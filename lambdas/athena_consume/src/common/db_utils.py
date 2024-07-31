import pg8000


def get_pg_client(
    user: str,
    host: str,
    port: int,
    db: str,
    pwd: str,
    auto_commit=True,
    ssl=False,
):
    client = pg8000.connect(
        user=user, host=host, port=port, database=db, password=pwd, ssl=ssl
    )
    client.autocommit = auto_commit
    cur = client.cursor()
    return client, cur


def redshift_base_copy_cmd(table: str, bucket: str, key: str, iam_role: str) -> str:
    """Base skeleton of any Redshift COPY Command"""
    return """
            COPY {table}
            FROM 's3://{bucket}/{key}'
            IAM_ROLE '{iam_role}'
            """.format(
        table=table, bucket=bucket, key=key, iam_role=iam_role
    )


def redshift_basic_csv_copy_cmd(
    table: str, bucket: str, key: str, iam_role: str
) -> str:
    base_qry = redshift_base_copy_cmd(
        table=table, bucket=bucket, key=key, iam_role=iam_role
    )
    return "{base_query} delimiter '{delimiter}' IGNOREHEADER 1".format(
        base_query=base_qry, delimiter=","
    )


def redshift_build_copy_cmd(
    table: str, bucket: str, key: str, iam_role: str, options: str
) -> str:
    base_qry = redshift_base_copy_cmd(
        table=table, bucket=bucket, key=key, iam_role=iam_role
    )
    return "{base_query} {options}".format(base_query=base_qry, options=options)
