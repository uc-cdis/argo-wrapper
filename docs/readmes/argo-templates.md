## Argo templates

### overview

Argo templates are workflows that can be referenced by other workflows. In the VA we use this capability to version our GWAS workflows. Currently we version by appending the latest git hash to the workflow template name. Workflows themselves are stored [here](https://github.com/uc-cdis/vadc-genesis-cwl/tree/master/argo/gwas-workflows)

### Adding a new workflow template to data commons

1. scp the new template.yaml to the data commons you want to add it to.
2. ssh onto the enviorment and run `argo template create -n argo {location_of_the_template_yaml}`
3. confirm that the template is created via running `argo tempalte list -n argo`, you should see the name of the new template you created
4. If you need to make changes run `argo template delete -n argo {template_name}` and then repeat steps 1-3
