# SSL Certificate Setup Guide for E2B

This guide explains how to ensure SSL certificates are properly configured on remote machines for E2B cloud sandbox integration.

## Quick SSL Certificate Check

Run this on any machine to verify SSL certificates:

```bash
# Test if SSL certificates are working
python -c "import ssl; import urllib.request; urllib.request.urlopen('https://api.e2b.dev')"

# If successful, prints nothing (exit code 0)
# If failed, shows: "SSL: CERTIFICATE_VERIFY_FAILED"
```

## SSL Certificate Setup by Environment

### Ubuntu/Debian (Most Common)

```bash
# Update system certificates
sudo apt-get update
sudo apt-get install -y ca-certificates

# Update Python SSL certificates
pip install --upgrade certifi

# Verify installation
python -c "import certifi; print('Certificates location:', certifi.where())"
```

### CentOS/RHEL/Rocky Linux

```bash
# Update system certificates
sudo yum update ca-certificates

# Update Python SSL certificates
pip install --upgrade certifi

# Verify
python -c "import certifi; print('Certificates location:', certifi.where())"
```

### macOS (Anaconda/Homebrew Python)

```bash
# Option 1: Update certifi package
pip install --upgrade certifi

# Option 2: Install system certificates (for standard Python)
/Applications/Python\ 3.11/Install\ Certificates.command

# Option 3: For Anaconda Python
conda install -c conda-forge ca-certificates certifi openssl

# Verify
python -c "import certifi; print('Certificates location:', certifi.where())"
```

### Docker Containers

Add this to your Dockerfile:

```dockerfile
# Install system certificates
RUN apt-get update && apt-get install -y ca-certificates

# Install Python certificates
RUN pip install --upgrade certifi

# Verify SSL works
RUN python -c "import ssl; print('SSL configured')"
```

### GitHub Actions / CI/CD

Add this to your workflow:

```yaml
- name: Setup SSL Certificates
  run: |
    pip install --upgrade certifi
    python -c "import certifi; print('Certificates OK')"
```

## Environment-Specific E2B Setup

### Development (Local Machine)

1. Install E2B SDK:
```bash
pip install "e2b-code-interpreter>=0.2.0"
```

2. Set API key:
```bash
export E2B_API_KEY="your-key-from-dashboard"
```

3. Test connection:
```bash
python -c "from e2b_code_interpreter import Sandbox; print('E2B SDK installed')"
```

### Production (Remote Server)

1. **Install certificates first**:
```bash
# Ubuntu/Debian
sudo apt-get install -y ca-certificates
pip install --upgrade certifi

# Verify
python -c "import ssl; import urllib.request; urllib.request.urlopen('https://api.e2b.dev')"
```

2. **Install E2B SDK**:
```bash
pip install "e2b-code-interpreter>=0.2.0"
```

3. **Set API key persistently**:
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export E2B_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

4. **Test E2B connection**:
```bash
E2B_API_KEY="your-key" python -c "
from e2b_code_interpreter import Sandbox
with Sandbox.create() as sandbox:
    print('✅ E2B connection successful')
"
```

### Docker Deployment

Complete Dockerfile example:

```dockerfile
FROM python:3.11-slim

# Install system certificates
RUN apt-get update && \
    apt-get install -y ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --upgrade certifi

# Verify SSL
RUN python -c "import ssl; print('SSL configured')"

# Set working directory
WORKDIR /app
COPY . .

# E2B API key will be provided at runtime via environment variable
ENV E2B_API_KEY=""

CMD ["python", "your_app.py"]
```

Run with:
```bash
docker run -e E2B_API_KEY="your-key" your-image
```

## Troubleshooting

### Error: "SSL: CERTIFICATE_VERIFY_FAILED"

**Cause**: Python can't find SSL certificates

**Fix**:
```bash
# Update certifi
pip install --upgrade certifi

# Set explicit certificate path
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")

# Or update system certificates
sudo apt-get install --reinstall ca-certificates  # Ubuntu/Debian
```

### Error: "certificate verify failed: unable to get local issuer certificate"

**Cause**: Outdated CA certificates

**Fix**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install --reinstall ca-certificates

# Python
pip install --upgrade certifi

# Verify
python -c "import requests; requests.get('https://api.e2b.dev')"
```

### Error: "E2B_API_KEY not set"

**Cause**: Environment variable not configured

**Fix**:
```bash
# Temporary (current session)
export E2B_API_KEY="your-key"

# Persistent (add to shell config)
echo 'export E2B_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

## Testing SSL Configuration

### Test 1: System SSL

```bash
python -c "
import ssl
import urllib.request

try:
    urllib.request.urlopen('https://api.e2b.dev')
    print('✅ System SSL working')
except Exception as e:
    print('❌ SSL failed:', e)
"
```

### Test 2: Python certifi

```bash
python -c "
import certifi
import requests

try:
    response = requests.get('https://api.e2b.dev', verify=certifi.where())
    print('✅ Python certifi working')
except Exception as e:
    print('❌ certifi failed:', e)
"
```

### Test 3: E2B Connection

```bash
E2B_API_KEY="your-key" python -c "
from e2b_code_interpreter import Sandbox

try:
    # This will fail gracefully if API key is invalid
    # But SSL error will be different
    with Sandbox.create() as sandbox:
        print('✅ E2B connection working')
except Exception as e:
    if 'SSL' in str(e) or 'certificate' in str(e).lower():
        print('❌ SSL error:', e)
    else:
        print('⚠️  Connection error (may be API key):', e)
"
```

## Best Practices

1. **Always use latest certifi**: `pip install --upgrade certifi`
2. **Keep system updated**: Regularly update CA certificates
3. **Environment variables**: Set `E2B_API_KEY` via environment, not code
4. **Docker**: Use official Python base images with certificates pre-installed
5. **CI/CD**: Install certificates as first step in pipeline
6. **Security**: Never commit API keys to git, use environment variables or secrets management

## NAT Workflow Configuration

For NAT workflows using E2B:

```yaml
functions:
  e2b_code_execution:
    _type: e2b_code_execution
    e2b_api_key: "${E2B_API_KEY}"  # From environment variable
    workspace_files_dir: "output_data"
    timeout: 30.0

  code_generation_assistant:
    _type: code_generation_assistant
    llm_name: "coding_llm"
    code_execution_tool: "e2b_code_execution"  # Use E2B instead of local
    output_folder: "output_data"
```

Run workflow:
```bash
export E2B_API_KEY="your-key"
nat run --config_file config.yaml --input "your query"
```

## Summary Checklist

Before deploying to a remote machine:

- [ ] System CA certificates installed (`ca-certificates` package)
- [ ] Python certifi updated (`pip install --upgrade certifi`)
- [ ] SSL test passes (test with `urllib.request.urlopen('https://api.e2b.dev')`)
- [ ] E2B SDK installed (`pip install e2b-code-interpreter`)
- [ ] E2B_API_KEY environment variable set
- [ ] Test E2B connection works (`Sandbox.create()`)
- [ ] NAT workflow configured correctly
- [ ] Docker containers have certificates (if using Docker)

---

**Note**: The Asset Lifecycle Management example uses **local Docker sandbox by default**, so E2B and SSL are optional. E2B is provided as an alternative for cloud-based code execution.
