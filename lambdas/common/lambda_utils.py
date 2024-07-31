"""
    Common utils shared across lambda functions
"""

import boto3
from csv import DictWriter
from datetime import datetime as dt, timedelta, date
from logging import Logger
import re
import requests
import os
from typing import List, Dict, Any, Tuple, Optional


TOKEN_URL: str = "https://identity.vwgroup.io/oidc/v1/token"
SEPARATOR: str = "@@@"


class APIError(Exception):
    """An API Error Exception"""

    def __init__(self, task, status):
        self.status = status
        self.task = task

    def __str__(self):
        return "APIError: status={} request={}".format(self.status, self.task)


def get_token(payload, url):
    token_request_resp = requests.post(url, data=payload)
    if token_request_resp.status_code != 200:
        # This means something went wrong.
        print(token_request_resp)
        raise APIError("POST Token", token_request_resp.status_code)

    token_request_res = token_request_resp.json()

    if "access_token" in token_request_res:
        return token_request_res["access_token"]
    else:
        raise APIError("Access Token not provided", "")


def get_token_payload(client_id_key: str, client_secret: str):
    # Credentials to get a token
    return [
        ("grant_type", "client_credentials"),
        ("client_id", get_ssm_parameter(os.environ.get(client_id_key))),
        ("client_secret", get_ssm_parameter(os.environ.get(client_secret))),
    ]


def get_payload_and_token(
    client_id_key: str = "CLIENT_ID",
    client_secret: str = "CLIENT_SECRET",
    url: str = TOKEN_URL,
):
    payload = get_token_payload(
        client_id_key=client_id_key, client_secret=client_secret
    )
    return get_token(payload, url)


def get_header_token(
    client_id_key: str = "CLIENT_ID",
    client_secret: str = "CLIENT_SECRET",
    url: str = TOKEN_URL,
) -> Dict[str, str]:
    token = get_payload_and_token(
        client_id_key=client_id_key, client_secret=client_secret, url=url
    )
    return {"Authorization": "Bearer {}".format(token)}


def get_data_raw(url, header, params):
    resp = requests.get(url, headers=header, params=params)
    if resp.status_code != 200:
        # This means something went wrong.
        raise APIError(
            "Failed to retrieve data from {}: {}".format(url, resp.text),
            resp.status_code,
        )
    return resp


def get_data(url, header, params):
    resp = get_data_raw(url=url, header=header, params=params)
    return resp.json()


def get_ssm_parameter(db_param: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")
    res = ssm.get_parameter(Name=db_param, WithDecryption=with_decryption)
    if res and res.get("Parameter", {}).get("Value"):
        return res["Parameter"]["Value"]
    raise Exception("Failed to retrieve terraform parameter: {}".format(res))


def sink_s3(prefix: str, file_name: str, bucket: str, local_path: str) -> str:
    """Uploads a local file to a given prefix in S3"""
    s3_key = "{}/{}".format(prefix, file_name)
    s3_client = boto3.resource("s3")
    s3_client.Bucket(bucket).upload_file(local_path, s3_key)
    return s3_key


def sink_csv(file_name: str, data: List[Dict[str, Any]]) -> None:
    """Writes CSV locally"""
    with open(file_name, "w") as csvfile:
        fieldnames = data[0].keys()
        writer = DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def _preprocess_file_name(file: str) -> Tuple[str, str]:
    _file_date_lst = file.split(SEPARATOR)
    file, date = _file_date_lst[0], None
    if len(_file_date_lst) > 1:
        date = _file_date_lst[1]
    return file, date


def pack_results(
    files: List[str],
    bucket: str,
    step_function_triggered: bool = True,
    errors: Optional[Dict[Any, Any]] = None,
):
    """Packs results so that both event triggered and Step Function can trigger AWS Redshift Lambda"""
    records = []
    if files:
        for file in files:
            file, delete_query = _preprocess_file_name(file=file)
            records.append(
                {
                    "s3": {
                        "bucket": {"name": bucket},
                        "object": {"key": file},
                        "delete_query": delete_query,
                    }
                }
            )
    return {
        "data": {"execution": "done"},
        "Records": records,
        "StepFunctionTriggered": step_function_triggered,
        "Errors": 0 if not errors else errors,
    }


def remaining_lambda_execution_time(context, min_ms: int = 30000) -> bool:
    """validates if time left in Lambda execution context is higher than the minimum (in milliseconds)"""
    remaining_time = context.get_remaining_time_in_millis()
    return remaining_time > min_ms


def partition_by_date(root_dir: str, file_name: str, processed_date: date) -> str:
    """Utility function to extract date path to build a file system path to store target key"""
    _date = processed_date.strftime("%Y/%m/%d")
    return "{root}/{date}/{file}".format(root=root_dir, date=_date, file=file_name)


def extract_date_range(
    event: Dict[str, str], logger: Optional[Logger] = None
) -> List[str]:
    """
    Date extraction utility function to extract the dates in between a date range (with optional
    logging side-effects)
    Expects event to be of the form: {"from_date": "Y-m-d", "to_date":"Y-m-d"}, [...]}
    """
    if not isinstance(event, dict):
        raise ValueError("Expecting event parameter to be of type Map")
    from_date = event.get("from_date")
    to_date = event.get("to_date")
    if not from_date or len(from_date) < 8 or not to_date or len(to_date) < 8:
        return []
    if isinstance(logger, Logger):
        logger.info(
            "Received specific date to process from: {} to: {}".format(
                from_date, to_date
            )
        )
    to_date = dt.strptime(to_date, "%Y-%m-%d").date()
    from_date = dt.strptime(from_date, "%Y-%m-%d").date()
    delta = to_date - from_date if from_date < to_date else from_date - to_date
    start_date = from_date if from_date < to_date else to_date
    return [
        (start_date + timedelta(d)).strftime("%Y-%m-%d") for d in range(delta.days + 1)
    ]


def snale_case(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
