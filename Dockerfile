FROM continuumio/miniconda3:24.7.1-0

WORKDIR /app

COPY environment.yml /app/environment.yml
RUN conda env create -f /app/environment.yml && conda clean -afy

SHELL ["conda", "run", "-n", "ifcservice", "/bin/bash", "-c"]

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["conda", "run", "--no-capture-output", "-n", "ifcservice", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
