"""This module contains the business logic of the function.

use the automation_context module to wrap your function in an Autamate context helper
"""

from pydantic import Field
from speckle_automate import (
    AutomateBase,
    AutomationContext,
    execute_automate_function,
)

from run import generate_all_objects

RESULT_BRANCH = "strava_automate"


class FunctionInputs(AutomateBase):
    """These are function author defined values.

    Automate will make sure to supply them matching the types specified here.
    Please use the pydantic model schema to define your inputs:
    https://docs.pydantic.dev/latest/usage/models/
    """

    client_id: str = Field(
        title="Client ID",
        description=(),
    )
    client_secret: str = Field(
        title="Client Secret",
        description=(),
    )
    activity_id: int = Field(
        title="Activity ID",
        description=(),
    )
    code: str = Field(
        title="Code from the URL",
        description=(),
    )


def automate_function(
    automate_context: AutomationContext,
    function_inputs: FunctionInputs,
) -> None:
    """This is an example Speckle Automate function.

    Args:
        automate_context: A context helper object, that carries relevant information
            about the runtime context of this function.
            It gives access to the Speckle project data, that triggered this run.
            It also has conveniece methods attach result data to the Speckle model.
        function_inputs: An instance object matching the defined schema.
    """
    # the context provides a conveniet way, to receive the triggering version
    try:
        project_id = automate_context.automation_run_data.project_id

        # create branch if needed
        existing_branch = automate_context.speckle_client.branch.get(
            project_id, RESULT_BRANCH, 1
        )
        if existing_branch is None:
            br_id = automate_context.speckle_client.branch.create(
                stream_id=project_id, name=RESULT_BRANCH, description=""
            )
        else:
            br_id = existing_branch.id

        client_id = function_inputs.client_id
        client_secret = function_inputs.client_secret
        activity_id = function_inputs.activity_id
        code = function_inputs.code

        commitObj = generate_all_objects(client_id, client_secret, activity_id, code)
        automate_context.create_new_version_in_project(
            commitObj, br_id, "Context from Automate"
        )
        print(
            f"Created id={automate_context._automation_result.result_versions[len(automate_context._automation_result.result_versions)-1]}"
        )
        automate_context._automation_result.result_view = f"{automate_context.automation_run_data.speckle_server_url}/projects/{automate_context.automation_run_data.project_id}/models/{automate_context.automation_run_data.model_id}"

        automate_context.mark_run_success("No forbidden types found.")
    except Exception as ex:
        automate_context.mark_run_failed(f"Failed to create 3d context cause: {ex}")

    # if the function generates file results, this is how it can be
    # attached to the Speckle project / model
    # automate_context.store_file_result("./report.pdf")


def automate_function_without_inputs(automate_context: AutomationContext) -> None:
    """A function example without inputs.

    If your function does not need any input variables,
     besides what the automation context provides,
     the inputs argument can be omitted.
    """
    pass


# make sure to call the function with the executor
if __name__ == "__main__":
    # NOTE: always pass in the automate function by its reference, do not invoke it!

    # pass in the function reference with the inputs schema to the executor
    execute_automate_function(automate_function, FunctionInputs)

    # if the function has no arguments, the executor can handle it like so
    # execute_automate_function(automate_function_without_inputs)
