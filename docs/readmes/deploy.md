## How to deploy Argo-wrapper in a Gen3 environment

### Prereq's

1. Make sure that argo-engine is alredy deployed. if not run `gen3 kube-setup-argo`

### Deployment

2. Deploy the Argo-wrapper server by adding it to the manifest.json of the enviorment then run `gen3 roll argo-wrapper`

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
