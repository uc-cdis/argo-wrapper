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
curl -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons-url}/ga4gh/wes/v2/status/{workflow_id}
```

5. Cancel workflow
```
curl -X POST  -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons-url}/ga4gh/wes/v2/cancel/{workflow_id}
```

6. Fetch all workflows ran by yourself
```
curl -H "Content-Type: application/json" -H "$(cat prod_auth)" https://{commons_url}/ga4gh/wes/v2/workflows
```

7. Cancel a run that's currently in-progress
```
curl -d "@request_body.json" -X POST -H "$(cat auth)" https://<replaceme>.planx-pla.net/ga4gh/wes/v1/runs/<runID>/cancel
