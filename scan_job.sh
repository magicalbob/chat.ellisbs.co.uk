rm -rf __pycache__
docker run -e SONAR_HOST_URL="https://sonarqube.ellisbs.co.uk" -e SONAR_LOGIN="sqp_3e15c2713c0427caeea973d7001e2346de5529a4" -v "$(pwd):/usr/src" sonarsource/sonar-scanner-cli
