# argo-wrapper
sdf

argo-wrapper is a service that faciliatates argo-engine to interact with GWAS front-end

## Functionalites

* authenticates user to make sure they have permission to run workflows in argo-engine
* APIs
    * Submit workflow
    * Retireve workflow info
    * cancel(delete) workflow
    * See workflows ran by user


* Permissions
    * currently there is 1 permission called [workflow_admin](https://github.com/uc-cdis/commons-users/blob/master/users/vhdcprod/user.yaml#L69-L72) that grants users
    the ability to all 4 apis.
