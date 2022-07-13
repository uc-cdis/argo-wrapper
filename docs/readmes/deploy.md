## How to deploy Argo-wrapper in a Gen3 environment

### Prereq's

1. Make sure that argo-engine is alredy deployed. if not please refer to [Argo Engine](argo-engine.md)

### Deployment to a commons that already has argo-wrapper installed

2. Check if argo-wrapper is deployment to your commons via running `kubectl get pods | grep argo-wrapper`. If a pod is returned via the previous command then to redeploy run `gen3 delete deployment.apps argo-wrapper-deployment && gen3 roll argo-wrapper `

### Deployment to an data commons that does not have argo-wrapper installed

3. Add argo-wrapper to the manifest.json of the enviorment. If in qa then the enviorment manifests are stored [here](https://github.com/uc-cdis/gitops-qa). If a production enviorment then [here](https://github.com/uc-cdis/cdis-manifest). After that ssh onto the enviorment and run `gen3 roll argo-wrapper`

### Auth and User YAML

4. Argo-wrapper utilizes Gen3's policy engine, [Arborist](https://github.com/uc-cdis/arborist), for authorization. It is defined as the following in qa-mickey:
    1. Role
        ```yaml
            - id: 'workflow_admin'
              permissions:
                - id: 'argo_access'
                  action:
                    service: 'argo_workflow'
                    method: 'access'
        ```

5. Give the `workflow_admin` policy to those users who need it.
```yaml
    policies:
    - workflow_admin
```
