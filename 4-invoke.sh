#!/bin/bash
if ! hash aws 2>/dev/null; then
    echo "This script requires the AWS cli installed"
    exit 2
fi

set -eo pipefail

# while true; do
#   aws lambda invoke --function-name lambda-eks-getpods-python --payload '{}' out.json
#   cat out.json
#   echo ""
#   sleep 2
# done

aws lambda invoke --function-name lambda-eks-getpods-python --cli-binary-format raw-in-base64-out --payload file://invoke-namespaces-payload.json namespaces-out.json
cat namespaces-out.json
echo ""
sleep 2

aws lambda invoke --function-name lambda-eks-getpods-python --cli-binary-format raw-in-base64-out --payload file://invoke-pods-payload.json  pods-out.json
cat pods-out.json
echo ""
sleep 2
