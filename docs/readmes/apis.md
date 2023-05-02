## How to use Argo-wrapper apis

1. Download an api key from your commons profile page

2. Fetch token using API key

```
echo Authorization: bearer $(curl -d '{"api_key": "<replaceme>", "key_id": "<replaceme>"}' -X POST -H "Content-Type: application/json" https://{commons-url}/user/credentials/api/access_token | jq .access_token | sed 's/"//g') > auth # pragma: allowlist secret
```

3. POST the workflow submission
```
curl -d "@prod_body.json" -X POST -H "Content-Type: application/json" -H "$(cat qa_auth)" https://{commons-url}/ga4gh/wes/v2/submit
```

4. Check workflow status
```
curl -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons-url}/ga4gh/wes/v2/status/{workflow_id}?uid={workflow_uid}
```

5. Cancel workflow
```
curl -X POST  -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons-url}/ga4gh/wes/v2/cancel/{workflow_id}
```

6. Fetch all workflows ran by yourself
```
curl -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons_url}/ga4gh/wes/v2/workflows
```

7. Retry a failed workflow
```
curl -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons-url}/ga4gh/wes/v2/retry/{workflow_id}?uid={workflow_uid}
```

8. Check the logs of a workflow
```
curl -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons-url}/ga4gh/wes/v2/logs/{workflow_id}?uid={workflow_uid}
```
