FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

RUN python -m pip install --no-cache-dir \
    black==26.5.1 \
    flake8==7.4.1 \
    ruff==0.15.7 \
    mypy==1.18.2
