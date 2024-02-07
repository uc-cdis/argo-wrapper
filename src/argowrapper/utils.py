import requests
from argowrapper import logger


def get_team_cohort_id(token, source_id, team_project):
    header = {"Authorization": token, "cookie": "fence={}".format(token)}
    url = "http://cohort-middleware-service/cohortdefinition-stats/by-source-id/{}/by-team-project?team-project={}".format(
        source_id, team_project
    )

    try:
        r = requests.get(url=url, headers=header)
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