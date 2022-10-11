## How to deploy Argo-wrapper in a Gen3 environment

### Pre-requisites

Make sure that argo-engine is already deployed. If not, please refer to [Argo Engine](argo-engine.md)

### (One time only) pre-deployment steps for a data commons that does not yet have argo-wrapper installed

Add argo-wrapper to the manifest.json of the environment:

- If in qa then the environment manifests are stored [here](https://github.com/uc-cdis/gitops-qa).
- If a production environment then [here](https://github.com/uc-cdis/cdis-manifest).

After that, run deployment steps listed in the subsection below.

### Deployment steps

Connect (ssh) to the environment and deploy from the command line using:

```
echo "====== Pull manifest without going into directory ====== "
git -C ~/cdis-manifest pull
echo "====== Update the manifest configmaps ======"
gen3 kube-setup-secrets
echo "====== Deploy ======"
gen3 roll argo-wrapper
```

Check if argo-wrapper is up and running using:

```
kubectl get pods | grep argo-wrapper`
```

### Auth and User YAML

1. Argo-wrapper utilizes Gen3's policy engine, [Arborist](https://github.com/uc-cdis/arborist), for authorization. It is defined as the following in qa-mickey:
    1. Role
        ```yaml
            - id: 'workflow_admin'
              permissions:
                - id: 'argo_access'
                  action:
                    service: 'argo_workflow'
                    method: 'access'
        ```

2. Assign the `workflow_admin` policy to the user whom should be granted permission for submitting Argo workflows through argo-wrapper:
```yaml
    policies:
    - workflow_admin
```
