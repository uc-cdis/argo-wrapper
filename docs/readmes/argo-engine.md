## Argo Engine

### Overview

Argo engine is the internal name we use for [argo workflow](https://github.com/argoproj/argo-workflows). It is an external open source tool that we utilize to run GWAS workflows.

### Deployment

* Deployment script for argo engine is located [here](https://github.com/uc-cdis/cloud-automation/blob/master/gen3/bin/kube-setup-argo.sh)
* To deploy ssh into a data commons and run `gen3 kube-setup-argo`. Argo engine will automatically be deployment to the namespace argo
