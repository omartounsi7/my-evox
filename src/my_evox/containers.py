"""Evaluator containers: every solution is evaluated in its problem's Docker container (D3, D10).

The problem's image is built from its evaluator folder (skydiscover's container protocol: a
Dockerfile, and an evaluate.sh that receives a program's path and prints JSON) the first time it
is needed, and tagged with a hash of the folder, so that a changed folder gets a new image. A run
starts one long-lived container from it. Each child is copied into the container's /tmp and
evaluated there by evaluate.sh, as skydiscover does, within the problem's time limit.

The container has no network, a read-only file system except /tmp, limits on memory and
processes, and no privileges, so that whatever the solution model's code does stays inside it.
Every container is labelled with the run's id. The run removes all of them when it stops, and at
start-up removes any left by an earlier session of the same run, so that none outlives its run.
"""

import hashlib
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from my_evox.evaluator import Runner, RunOutput
from my_evox.problem import Problem

# The images' name; each problem's tag is a hash of its evaluator folder
IMAGE_REPOSITORY = "my-evox-evaluator"
# The label that marks a run's containers, so that all of them can be found and removed
RUN_LABEL = "my-evox.run"
# The container's limits: memory (without swap), processes and threads, and the size of /tmp
MEMORY_LIMIT = "2g"
MAX_PROCESSES = 256
TMP_SIZE = "512m"
# Where skydiscover's Dockerfiles put the evaluator, and the mode its evaluate.sh receives
EVALUATE_SCRIPT = "/benchmark/evaluate.sh"
EVALUATION_MODE = "train"
# Seconds the timeout command waits, once the time limit is reached, before killing everything
KILL_AFTER_SECONDS = 5
# Exit codes of the timeout command when it stopped the evaluation: 124 when the evaluation ended
# on SIGTERM, 137 when it had to be killed
TIMEOUT_EXIT_CODES = (124, 137)
# The exit code of a process killed with SIGKILL, as the memory limit kills
KILLED_EXIT_CODE = 137
# Seconds docker exec may take beyond the time limit before the run stops waiting for it
DOCKER_GRACE_SECONDS = 60
# Seconds the other docker commands may take; building an image takes much longer
DOCKER_COMMAND_SECONDS = 120
BUILD_SECONDS = 3600
# The longest part of Docker's output kept in an error message
MAX_DOCKER_OUTPUT = 3000


class ContainerError(Exception):
    """Raised when Docker is missing, stopped, or cannot do what is asked; the message says how."""


class ContainerRunner(Runner):
    """Runs a problem's evaluator inside one long-lived container (D10)."""

    def __init__(self, container_id: str, run_id: str, extension: str, time_limit: float) -> None:
        super().__init__(extension, time_limit)
        # The container the evaluations run in
        self.container_id: str = container_id
        # The run's id, which labels its containers
        self.run_id: str = run_id

    @classmethod
    def start(cls, problem: Problem, run_id: str) -> "ContainerRunner":
        """Build the problem's image if needed, and start the run's container from it.

        Raises ContainerError if Docker is missing or stopped, or if the image does not build.
        """
        check_docker_running()
        image = ensure_image(problem.evaluator_folder)
        # Containers left by an earlier session of this run, if it was killed, go first.
        remove_run_containers(run_id)
        container_id = start_container(image, run_id)
        extension = problem.initial_program.suffix
        return cls(container_id, run_id, extension, problem.evaluation.timeout)

    def run(self, code: str) -> RunOutput:
        """Copy the code into the container's /tmp, run evaluate.sh on it, and remove it."""
        path = f"/tmp/{uuid.uuid4().hex}{self.extension}"
        self.copy_in(code, path)
        try:
            return self.evaluate_file(path)
        finally:
            docker(["exec", self.container_id, "rm", "-f", path], DOCKER_COMMAND_SECONDS)

    def copy_in(self, code: str, path: str) -> None:
        """Write the code to a file in the container, through docker exec's standard input."""
        command = ["exec", "--interactive", self.container_id, "sh", "-c", 'cat > "$1"', "sh", path]
        copied = docker(command, DOCKER_COMMAND_SECONDS, input_text=code)
        if copied.returncode != 0:
            raise ContainerError(f"copying a program into the container failed: {tail(copied)}")

    def evaluate_file(self, path: str) -> RunOutput:
        """Run evaluate.sh on the program file, stopped by the timeout command at the time limit.

        The timeout command stops the evaluation's whole process group, so that a program that
        never ends leaves nothing running in the container.
        """
        limit = f"{self.time_limit:g}"
        command = ["exec", self.container_id, "timeout", f"--kill-after={KILL_AFTER_SECONDS}"]
        command += [limit, EVALUATE_SCRIPT, path, EVALUATION_MODE]
        started = time.monotonic()
        try:
            completed = docker(command, self.time_limit + DOCKER_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            message = "docker exec did not answer, even after the time limit and a grace period"
            return RunOutput("", message, None, time.monotonic() - started)
        seconds = time.monotonic() - started
        return run_output(completed, seconds, self.time_limit)

    def close(self) -> None:
        """Stop and remove every container of the run."""
        remove_run_containers(self.run_id)


def run_output(
    completed: subprocess.CompletedProcess[str], seconds: float, limit: float
) -> RunOutput:
    """Return what an evaluation in the container printed, and how it ended.

    The timeout command exits with 124 or 137 when it stopped the evaluation; 137 before the
    time limit means something else killed it, most likely the memory limit.
    """
    code = completed.returncode
    timed_out = code in TIMEOUT_EXIT_CODES and seconds >= limit
    killed = code == KILLED_EXIT_CODE and not timed_out
    return RunOutput(completed.stdout, completed.stderr, code, seconds, timed_out, killed)


def docker(
    arguments: list[str], timeout: float, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a docker command and return how it went. Raises ContainerError if Docker is missing.

    A command that takes longer than timeout seconds raises subprocess.TimeoutExpired.
    """
    if shutil.which("docker") is None:
        raise ContainerError("Docker is not installed; install Docker Desktop or Docker Engine")
    return subprocess.run(
        ["docker", *arguments],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def check_docker_running() -> None:
    """Raise ContainerError if Docker is missing, or installed but not running."""
    info = docker(["info", "--format", "{{.ServerVersion}}"], DOCKER_COMMAND_SECONDS)
    if info.returncode != 0:
        raise ContainerError(f"Docker is not running; start it. Docker said: {tail(info)}")


def ensure_image(folder: Path) -> str:
    """Build the image of an evaluator folder unless it exists, and return its tag.

    Raises ContainerError if the build fails.
    """
    tag = f"{IMAGE_REPOSITORY}:{folder_hash(folder)}"
    if docker(["image", "inspect", tag], DOCKER_COMMAND_SECONDS).returncode == 0:
        return tag
    print(f"Building the evaluator's image {tag} from {folder}; the first time takes minutes...")
    built = docker(["build", "--tag", tag, str(folder)], BUILD_SECONDS)
    if built.returncode != 0:
        raise ContainerError(f"building the image of {folder} failed:\n{tail(built)}")
    return tag


def folder_hash(folder: Path) -> str:
    """Return a short hash of every file in the folder, names included, in a fixed order."""
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(folder).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def start_container(image: str, run_id: str) -> str:
    """Start the run's container from the image, idle until evaluations are run in it.

    Returns the container's id. Raises ContainerError if it does not start.
    """
    isolation = [
        "--network", "none",
        "--read-only",
        "--tmpfs", f"/tmp:rw,exec,size={TMP_SIZE}",
        "--memory", MEMORY_LIMIT,
        "--memory-swap", MEMORY_LIMIT,
        "--pids-limit", str(MAX_PROCESSES),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        # Libraries that write caches into the home folder find one they may write to.
        "--env", "HOME=/tmp",
    ]  # fmt: skip
    command = ["run", "--detach", "--rm", "--label", f"{RUN_LABEL}={run_id}", *isolation]
    command += ["--entrypoint", "sleep", image, "infinity"]
    started = docker(command, DOCKER_COMMAND_SECONDS)
    if started.returncode != 0:
        raise ContainerError(f"the evaluator's container did not start: {tail(started)}")
    return started.stdout.strip()


def run_containers(run_id: str) -> list[str]:
    """Return the ids of every container of the run, running or not."""
    label = f"label={RUN_LABEL}={run_id}"
    listed = docker(["ps", "--all", "--quiet", "--filter", label], DOCKER_COMMAND_SECONDS)
    return listed.stdout.split()


def remove_run_containers(run_id: str) -> None:
    """Remove every container of the run, running or not."""
    containers = run_containers(run_id)
    if containers:
        docker(["rm", "--force", *containers], DOCKER_COMMAND_SECONDS)


def tail(completed: subprocess.CompletedProcess[str]) -> str:
    """Return the end of what a docker command printed, where its error is."""
    output = (completed.stdout + completed.stderr).strip()
    return output[-MAX_DOCKER_OUTPUT:] or "(nothing)"
