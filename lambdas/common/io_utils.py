"""
    Common IO utils
"""
from logging import Logger

from abc import ABCMeta, abstractmethod
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from botocore.response import StreamingBody


class AwsLogger(object):
    """
    Digests AWS Boto exceptions into log
    for all error codes see
    https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html
    """

    def __init__(self, logger: Logger, msg_prefix: str):
        self._logger = logger
        self._msg_prefix = msg_prefix

    def info(self, msg):
        self._logger.info(msg)

    def error(self, msg):
        self._logger.error(msg)

    def debug(self, msg):
        self._logger.debug(msg)

    def log_client_error(self, error: ClientError):
        code = error.response["Error"]["Code"]
        if code == "AccessDenied":
            self.error("{}: access denied - {}".format(self._msg_prefix, error))
        self.error(
            "{} - something wrong happened with error code {} - {}".format(
                self._msg_prefix, code, error
            )
        )


class StreamingObject(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def stream(self):
        raise NotImplementedError


class S3StreamingObject(StreamingObject):
    def __init__(self, client: BaseClient, bucket: str, key: str, logger: Logger):
        self._err_msg_prefix = "Failed to get S3 object from s3://{}/{}".format(
            bucket, key
        )
        self._logger = AwsLogger(logger=logger, msg_prefix=self._err_msg_prefix)
        try:
            self.obj: StreamingBody = client.get_object(Bucket=bucket, Key=key)
        except ClientError as e:
            self._logger.log_client_error(e)
            raise e

    def stream(self):
        for elm in self.obj["Body"]._raw_stream:
            yield elm
