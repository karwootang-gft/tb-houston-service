"""
This is the deployments module and supports all the ReST actions for the
solutions collection
"""

# 3rd party modules
from flask import make_response, jsonify, abort
from config import db, app
from models import Solution, SolutionSchema
from models import ModelTools
from extendedSchemas import ExtendedSolutionSchema
from extendedSchemas import SolutionDeploymentSchema
from extendedSchemas import SolutionNamesOnlySchema
import solution_extension
from pprint import pformat
import requests
import os
import json
from sqlalchemy import literal_column


def read_all(active=None, namesonly=None, page=None, page_size=None, sort=None):
    """
    This function responds to a request for /api/solutions
    with the complete lists of solutions

    :return:        json string of list of solutions
    """

    app.logger.debug("solution.read_all")
    app.logger.debug(f"Active: {active}, namesonly: {namesonly}")

    # pre-process sort instructions
    if (sort==None):
        solution_query = Solution.query.order_by(Solution.id)
    else:
        try:
            sort_inst = [ si.split(":") for si in sort ]
            orderby_arr = []
            for si in sort_inst:
                si1 = si[0]
                if len(si) > 1:
                    si2 = si[1]
                else:
                    si2 = "asc"
                orderby_arr.append(f"{si1} {si2}")
            #print("orderby: {}".format(orderby_arr))
            solution_query = Solution.query.order_by(literal_column(", ".join(orderby_arr)))
        except Exception as e:
            print("Exception: {}".format(pformat(e)))
            solution_query = Solution.query.order_by(Solution.id)

    # Create the list of solutions from our data
    if active != None:
      solution_query = solution_query.filter(Solution.active == active)

    # do limit and offset last
    if (page==None or page_size==None):
      solutions = solution_query.all()
    else:
      solutions = solution_query.limit(page_size).offset(page * page_size)

    if namesonly == True:
      # Serialize the data for the response
      schema = SolutionNamesOnlySchema(many=True)
      data = schema.dump(solutions)
    else:
      solutions_arr = []
      for sol in solutions:
        solutions_arr.append(solution_extension.build_solution(sol))
      app.logger.debug("solutions array:")
      app.logger.debug(pformat(solutions_arr))
      # Serialize the data for the response
      schema = ExtendedSolutionSchema(many=True)
      data = schema.dump(solutions_arr)

    app.logger.debug("solutions data:")
    app.logger.debug(data)
    return data, 200


def read_one(oid):
    """
    This function responds to a request for /api/solution/{oid}
    with one matching solution from solutions

    :param application:   id of solution to find
    :return:              solution matching id
    """

    sol = (Solution.query.filter(Solution.id == oid).one_or_none())

    if sol is not None:
        solution = solution_extension.build_solution(sol)
        # Serialize the data for the response
        solution_schema = ExtendedSolutionSchema()
        data = solution_schema.dump(solution)
        return data, 200
    else:
        abort(
            404, f"Solution with id {oid} not found".format(id=oid)
        )


def create(solutionDetails):
    """
    This function creates a new solution in the solutions list
    based on the passed in solutions data

    :param solution:  solution to create in solutions list
    :return:        201 on success, 406 on solutions exists
    """

    # Defaults
    if (solutionDetails.get('active') == None):
      solutionDetails['active'] = True

    if (solutionDetails.get('favourite') == None):
      solutionDetails['favourite'] = True

    if (solutionDetails.get('teams') == None):
      solutionDetails['teams'] = 0

    if (solutionDetails.get('deployed') == None):
      solutionDetails['deployed'] = False

    if (solutionDetails.get('deploymentState') == None):
      solutionDetails['deploymentState'] = ""

    if (solutionDetails.get('statusId') == None):
      solutionDetails['statusId'] = 0

    if (solutionDetails.get('statusCode') == None):
      solutionDetails['statusCode'] = ""

    if (solutionDetails.get('statusMessage') == None):
      solutionDetails['statusMessage'] = ""

    # Remove applications because Solutions don't have
    # any applications when they are first created
    if ('applications' in solutionDetails):
      del solutionDetails['applications']

    # we don't need the id, the is generated automatically on the database
    if ('id' in solutionDetails):
      del solutionDetails["id"]

    solutionDetails['lastUpdated'] = ModelTools.get_utc_timestamp()
    solutionDetails['environments'] = json.dumps(solutionDetails.get('environments') or [])

    print("Create name 2: " + solutionDetails['name'])

    schema = SolutionSchema(many=False)
    new_solution = schema.load(solutionDetails, session=db.session)
    db.session.add(new_solution)
    db.session.commit()

    print("Create name 3: " + new_solution.name)

    # Serialize and return the newly created solution
    # in the response

    print(pformat(solutionDetails['environments']))

    print("create solution")
    print(pformat(new_solution))
    print(pformat(new_solution.environments))

    schema = ExtendedSolutionSchema()
    data = schema.dump(new_solution)
    return data, 201


def update(oid, solutionDetails):
    """
    Updates an existing solutions in the solutions list.

    :param key:    key of the solutions to update in the solutions list
    :param solutions:   solutions to update
    :return:       updated solutions
    """

    app.logger.debug(solutionDetails)

    # Does the solutions exist in solutions list?
    existing_solution = Solution.query.filter(
            Solution.id == oid
    ).one_or_none()

    # Does solutions exist?

    if existing_solution is not None:
        solutionDetails['environments'] = json.dumps(solutionDetails.get('environments') or existing_solution.environments)
        schema = SolutionSchema()
        update_solution = schema.load(solutionDetails, session=db.session)
        update_solution.key = solutionDetails.get('id', oid)
        update_solution.lastUpdated = ModelTools.get_utc_timestamp()

        db.session.merge(update_solution)
        db.session.commit()

        # return the updted solutions in the response
        schema = ExtendedSolutionSchema(many=False)
        print(">>>>>  " + pformat(solutionDetails))
        solutionDetails['environments'] = json.loads(solutionDetails['environments'])
        data = schema.dump(solutionDetails)
        return data, 200

    # otherwise, nope, deployment doesn't exist, so that's an error
    else:
        abort(404, f"Solution not found")


def delete(oid):
    """
    This function deletes a solution from the solutions list

    :param key: id of the solutions to delete
    :return:    200 on successful delete, 404 if not found
    """
    # Does the solution to delete exist?
    existing_solution = Solution.query.filter(Solution.id == oid).one_or_none()

    # if found?
    if existing_solution is not None:
        db.session.delete(existing_solution)
        db.session.commit()

        return make_response(f"Solution {oid} successfully deleted", 200)

    # Otherwise, nope, solution to delete not found
    else:
        abort(404, f"Solution {oid} not found")


def deployment_read_all():
    """
    This function responds to a request for /api/solutiondeployments
    with the complete lists of deployed solutions

    :return:        json string of list of deployed solutions
                    id and deployed fields
    """

    app.logger.debug("solution.deployment_read_all")

    solutions = Solution.query.all()
    schema = SolutionDeploymentSchema(many=True)
    data = schema.dump(solutions)

    app.logger.debug("solutions data:")
    app.logger.debug(data)
    return data, 200


def deployment_read_one(oid):
    """
    This function responds to a request for /api/solutiondeployment/{oid}
    with one matching solution deployment from solutions

    :param application:   id of solution to find
    :return:              solution matching id
    """

    sol = (Solution.query.filter(Solution.id == oid).one_or_none())

    if sol is not None:
        # Serialize the data for the response
        solution_schema = SolutionDeploymentSchema(many=False)
        data = solution_schema.dump(sol)
        return data, 200
    else:
        abort(
            404, f"Solution with id {oid} not found".format(id=oid)
        )


def deployment_create(solutionDeploymentDetails):
    """
    This function queries a solution forwards the request to the DaC

    :param solution:  id
    :return:        201 on success, 406 if solution doesn't exist
    """

    app.logger.debug(pformat(solutionDeploymentDetails))
    oid = solutionDeploymentDetails['id'];
    sol_json_payload = read_one(oid)
    resp = sol_json_payload[0]
    print(pformat(resp))
    data = send_deployment_request_to_the_dac(resp)
    resp_json = data.json()
    print(pformat(resp_json))
    return resp_json, 201


def deployment_update(oid, solutionDeploymentDetails):
    """
    Updates an existing solutions in the solutions list with the deployed status.

    :param key:    id of the solution
    :param solutionDetails:   solution details to update
    :return:       updated solution
    """

    app.logger.debug(solutionDeploymentDetails)

    # Does the solutions exist in solutions list?
    existing_solution = Solution.query.filter(
            Solution.id == oid
    ).one_or_none()

    # Does solutions exist?

    if existing_solution is not None:
        schema = SolutionSchema(many=False)
        update_solution = schema.load(solutionDeploymentDetails, session=db.session)
        update_solution.id = oid
        update_solution.lastUpdated = ModelTools.get_utc_timestamp()
        update_solution.deployed = solutionDeploymentDetails.get('deployed', update_solution.deployed)
        update_solution.deploymentState = solutionDeploymentDetails.get('deploymentState', update_solution.deploymentState)
        update_solution.statusId = solutionDeploymentDetails.get('statusId', update_solution.statusId)
        update_solution.statusCode = solutionDeploymentDetails.get('statusCode', update_solution.statusCode)
        update_solution.statusMessage = solutionDeploymentDetails.get('statusMessage', update_solution.statusMessage)

        db.session.merge(update_solution)
        db.session.commit()

        # return the updted solutions in the response
        schema = SolutionDeploymentSchema(many=False)
        data = schema.dump(update_solution)
        return data, 200

    # otherwise, nope, deployment doesn't exist, so that's an error
    else:
        abort(404, f"Solution {oid} not found")


def send_deployment_request_to_the_dac(sol_json_payload):

    url = "http://" + os.environ['GCP_DAC_URL'] + "/api/solution/"

    print(f"url: {url}")
    print(f"data: {sol_json_payload}")
    headers = { 'Content-Type': "application/json" }
    response = requests.post(url, data=json.dumps(sol_json_payload), headers=headers)
    print(pformat(response))
    #resp_json = response.json()
    return response
