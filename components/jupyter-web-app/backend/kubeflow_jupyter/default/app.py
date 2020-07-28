from flask import Flask, request, jsonify, send_from_directory
from ..common.base_app import app as base
from ..common import utils, api

FLASK_URL_PREFIX = '/jupyter'
STATIC_FOLDER = './static'

app = Flask(__name__, static_url_path=FLASK_URL_PREFIX)
app.register_blueprint(base, url_prefix=FLASK_URL_PREFIX)
logger = utils.create_logger(__name__)

NOTEBOOK = "./kubeflow_jupyter/common/yaml/notebook.yaml"


# POSTers
@app.route(f"{FLASK_URL_PREFIX}/api/namespaces/<namespace>/notebooks", methods=["POST"])
def post_notebook(namespace):
    body = request.get_json()
    defaults = utils.spawner_ui_config()
    logger.info("Got Notebook: {}".format(body))

    notebook = utils.load_param_yaml(NOTEBOOK,
                                     name=body["name"],
                                     namespace=namespace,
                                     serviceAccount="default-editor")

    utils.set_notebook_image(notebook, body, defaults)
    utils.set_notebook_cpu(notebook, body, defaults)
    utils.set_notebook_memory(notebook, body, defaults)
    utils.set_notebook_gpus(notebook, body, defaults)
    utils.set_notebook_configurations(notebook, body, defaults)

    # Workspace Volume
    workspace_vol = utils.get_workspace_vol(body, defaults)
    if not body.get("noWorkspace", False) and workspace_vol["type"] == "New":
        # Create the PVC
        ws_pvc = utils.pvc_from_dict(workspace_vol, namespace)

        logger.info("Creating Workspace Volume: {}".format(ws_pvc.to_dict()))
        r = api.create_pvc(ws_pvc, namespace=namespace)
        if not r["success"]:
            return jsonify(r)

    if not body.get("noWorkspace", False) and workspace_vol["type"] != "None":
        utils.add_notebook_volume(
            notebook,
            workspace_vol["name"],
            workspace_vol["name"],
            workspace_vol.get("path", defaults["workspaceVolume"]["value"]["mountPath"]["value"]),
        )

    # Add the Data Volumes
    for vol in utils.get_data_vols(body, defaults):
        if vol["type"] == "New":
            # Create the PVC
            dtvol_pvc = utils.pvc_from_dict(vol, namespace)

            logger.info("Creating Data Volume {}:".format(dtvol_pvc))
            r = api.create_pvc(dtvol_pvc, namespace=namespace)
            if not r["success"]:
                return jsonify(r)

        utils.add_notebook_volume(
            notebook,
            vol["name"],
            vol["name"],
            vol["path"]
        )

    # shm
    utils.set_notebook_shm(notebook, body, defaults)

    logger.info("Creating Notebook: {}".format(notebook))
    return jsonify(api.create_notebook(notebook, namespace=namespace))


# Since Angular is a SPA, we serve index.html every time
@app.route(f"{FLASK_URL_PREFIX}")
@app.route(f"{FLASK_URL_PREFIX}/")
def serve_root():
    return send_from_directory(STATIC_FOLDER, "index.html")

logger.info("==============")
logger.info(f"{STATIC_FOLDER}")
logger.info(f"{FLASK_URL_PREFIX}")
logger.info("==============")
logger.info(app.url_map)
logger.info("==============")
