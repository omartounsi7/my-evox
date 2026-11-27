# my-evox: the image of MinMaxMinDist's evaluator (see ../README.md). The paper's runs evaluated
# programs on their host, where skydiscover's "math" extra was installed; this image installs the
# same packages, at the versions skydiscover's first release locked for Python 3.12. torch comes
# from its CPU index: the container has no GPU, and the CPU build is far smaller.
FROM python:3.12-slim
WORKDIR /benchmark
RUN pip install --no-cache-dir torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x evaluate.sh
