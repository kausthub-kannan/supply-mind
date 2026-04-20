# Contributing to the Solution

## Setup
1. Install docker and docker-compose (would require WSL in Windows)
2. Run the below command to start docker compose
```bash
docker-compose up -d
```
 To shutdown the containers:
 ```bash
 docker-compose down -v
 ```

3. The env file will require below details
```.env
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
POSTGRES_PORT=

GMAIL_EMAIL=
GMAIL_PASSWORD=

TAVILY_API_KEY=

LITELLM_PORT=
LITELLM_API_URI=
LITELLM_API_KEY=

MISTRAL_API_KEY=

AGENTOPS_API_KEY=
```