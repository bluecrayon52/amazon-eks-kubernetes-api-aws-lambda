"Lambda function list pods in EKS cluster"
import base64
import os
import logging
import re
import boto3

from botocore.signers import RequestSigner
from kubernetes import client, config


logger = logging.getLogger()
logger.setLevel(logging.INFO)

STS_TOKEN_EXPIRES_IN = 60
session = boto3.session.Session()
sts = session.client('sts')
service_id = sts.meta.service_model.service_id
cluster_name = os.environ["CLUSTER_NAME"]
eks = boto3.client('eks')
cluster_cache = {}

def get_cluster_info():
    "Retrieve cluster endpoint and certificate"
    cluster_info = eks.describe_cluster(name=cluster_name)
    endpoint = cluster_info['cluster']['endpoint']
    cert_authority = cluster_info['cluster']['certificateAuthority']['data']
    cluster_info = {
        "endpoint" : endpoint,
        "ca" : cert_authority
    }
    return cluster_info

def get_bearer_token():
    "Create authentication token"
    signer = RequestSigner(
        service_id,
        session.region_name,
        'sts',
        'v4',
        session.get_credentials(),
        session.events
    )

    params = {
        'method': 'GET',
        'url': 'https://sts.{}.amazonaws.com/'
               '?Action=GetCallerIdentity&Version=2011-06-15'.format(session.region_name),
        'body': {},
        'headers': {
            'x-k8s-aws-id': cluster_name
        },
        'context': {}
    }

    signed_url = signer.generate_presigned_url(
        params,
        region_name=session.region_name,
        expires_in=STS_TOKEN_EXPIRES_IN,
        operation_name=''
    )
    base64_url = base64.urlsafe_b64encode(signed_url.encode('utf-8')).decode('utf-8')

    # remove any base64 encoding padding:
    return 'k8s-aws-v1.' + re.sub(r'=*', '', base64_url)

def lambda_handler(event, context):
    "Lambda handler"
    if cluster_name in cluster_cache:
        cluster = cluster_cache[cluster_name]
    else:
        # not present in cache retrieve cluster info from EKS service
        cluster = get_cluster_info()
        # store in cache for execution environment resuse
        cluster_cache[cluster_name] = cluster

    kubeconfig = {
        'apiVersion': 'v1',
        'clusters': [{
          'name': 'cluster1',
          'cluster': {
            'certificate-authority-data': cluster["ca"],
            'server': cluster["endpoint"]}
        }],
        'contexts': [{'name': 'context1', 'context': {'cluster': 'cluster1', "user": "user1"}}],
        'current-context': 'context1',
        'kind': 'Config',
        'preferences': {},
        'users': [{'name': 'user1', "user" : {'token': get_bearer_token()}}]
    }
    
    config.load_kube_config_from_dict(config_dict=kubeconfig)
    v1_api = client.CoreV1Api() # api_client
    
    # Extract the action group, api path, and parameters from the prediction
    action = event["actionGroup"]
    api_path = event["apiPath"]
    parameters = event["parameters"]
    inputText = event["inputText"]
    httpMethod = event["httpMethod"]
    
    if api_path.rsplit('/',1)[1] =='get-pods':
      namespace_name=parameters[0]["value"]
      pod_list = v1_api.list_namespaced_pod(namespace_name)
      body = [{"name": item.metadata.name, "state": item.status.phase} for item in pod_list.items ]
      response_code = 200
      response_body = {"application/json": {"body": str(body)}}
    
    elif api_path == '/namespaces':
      namespace_list = v1_api.list_namespace()
      body = [item.metadata.name for item in namespace_list.items]
      response_code = 200
      response_body = {"application/json": {"body": str(body)}}
      
    else: 
      body = {"{}::{} is not a valid api, try another one.".format(action, api_path)}
      response_code = 400
      response_body = {"application/json": {"body": str(body)}}
     
    
    action_response = {
        'actionGroup': action,
        'apiPath': api_path,
        'httpMethod': httpMethod,
        'httpStatusCode': response_code,
        'responseBody': response_body
    }
    
    session_attributes = event['sessionAttributes']
    prompt_session_attributes = event['promptSessionAttributes']
    
    api_response = {
        'messageVersion': '1.0', 
        'response': action_response,
        'sessionAttributes': session_attributes,
        'promptSessionAttributes': prompt_session_attributes
    }

# print(lambda_handler(None, None))

    return api_response
