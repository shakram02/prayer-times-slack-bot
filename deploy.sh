set -e
CONTAINER_TAG=prayer-times-slack-bot

echo "Deploying $CONTAINER_TAG..."
docker build -t $CONTAINER_TAG .
docker run -d $CONTAINER_TAG
printf "Your container name is:  \b"
docker ps --format "{{.Names}}" | awk 'FNR == 1'
