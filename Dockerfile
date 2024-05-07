FROM public.ecr.aws/lambda/python:3.11

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# # Ensure the directory exists and copy the modified cipher.py from your host to the container
RUN mkdir -p /var/lang/lib/python3.11/site-packages/pytube
COPY cipher.py /var/lang/lib/python3.11/site-packages/pytube/cipher.py

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD ["app.handler"]