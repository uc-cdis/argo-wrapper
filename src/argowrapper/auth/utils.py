import requests
from argowrapper import logger
from argowrapper.constants import COHORT_MIDDLEWARE_URL


def get_cohort_ids_for_team_project(token, source_id, team_project):
    header = {"Authorization": token, "cookie": "fence={}".format(token)}
    api_url = (
        COHORT_MIDDLEWARE_URL
        + "/cohortdefinition-stats/by-source-id/{}/by-team-project?team-project={}"
    )
    api_url = api_url.format(source_id, team_project)

    try:
        r = requests.get(url=api_url, headers=header)
        r.raise_for_status()
        team_cohort_info = r.json()
        team_cohort_id_set = set()
        if "cohort_definitions_and_stats" in team_cohort_info:
            for t in team_cohort_info["cohort_definitions_and_stats"]:
                if "cohort_definition_id" in t:
                    team_cohort_id_set.add(t["cohort_definition_id"])
        return team_cohort_id_set
    except Exception as e:
        exception = Exception("Could not get team project cohort ids", e)
        logger.error(exception)
        raise exception
