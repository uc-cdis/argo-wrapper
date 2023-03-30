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

### Quickstart with Helm

You can now deploy individual services via Helm!

If you are looking to deploy all Gen3 services, that can be done via the Gen3 Helm chart.
Instructions for deploying all Gen3 services with Helm can be found [here](https://github.com/uc-cdis/gen3-helm#readme).

To deploy the argo-wrapper service:
```bash
helm repo add gen3 https://helm.gen3.org
helm repo update
helm upgrade --install gen3/argo-wrapper
```
These commands will add the Gen3 helm chart repo and install the argo-wrapper service to your Kubernetes cluster.

Deploying argo-wrapper this way will use the defaults that are defined in this [values.yaml file](https://github.com/uc-cdis/gen3-helm/blob/master/helm/argo-wrapper/values.yaml)
You can learn more about these values by accessing the argo-wrapper [README.md](https://github.com/uc-cdis/gen3-helm/blob/master/helm/argo-wrapper/README.md)

If you would like to override any of the default values, simply copy the above values.yaml file into a local file and make any changes needed.

You can then supply your new values file with the following command:
```bash
helm upgrade --install gen3/argo-wrapper -f values.yaml
```

If you are using Docker Build to create new images for testing, you can deploy them via Helm by replacing the .image.repository value with the name of your local image.
You will also want to set the .image.pullPolicy to "never" so kubernetes will look locally for your image.
Here is an example:
```bash
image:
  repository: <image name from docker image ls>
  pullPolicy: Never
  # Overrides the image tag whose default is the chart appVersion.
  tag: ""
```

Re-run the following command to update your helm deployment to use the new image:
```bash
helm upgrade --install gen3/argo-wrapper
```

You can also store your images in a local registry. Kind and Minikube are popular for their local registries:
- https://kind.sigs.k8s.io/docs/user/local-registry/
- https://minikube.sigs.k8s.io/docs/handbook/registry/#enabling-insecure-registries

Dependencies:
- The argo-wrapper service utilizes Gen3's policy engine, [Arborist](https://github.com/uc-cdis/arborist) and [Fence](https://github.com/uc-cdis/fence), for authorization. Please review the "Quick Start with Helm" guides to deploy these two services.
