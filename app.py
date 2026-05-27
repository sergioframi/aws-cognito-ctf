import hashlib
import json
import uuid

import boto3
from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for

app = Flask(__name__)

# AWS Floci Configuration (VPS Target)
AWS_CONFIG = {
    "endpoint_url": "http://localhost:4566",
    "aws_access_key_id": "test",
    "aws_secret_access_key": "test",
    "region_name": "us-east-1",
}

FLAGS = {
    "lab1": "flag_1{gu3st_us3r_pr1vs}",
    "lab2": "flag_2{s3lf_s1gn_uP}",
    "lab3": "flag_3{aUth_Pr0t0c0l}",
    "lab4": "flag_4{On3_t3n4nt_for_4ll}",
}

LAB1_IDENTITY_POOL_ID = "us-east-1:lab1-identity-pool"
LAB1_BUCKET_NAME = "lab1-flag-bucket"
LAB1_OBJECT_KEY = "flag.txt"
LAB3_KNOWN_USER = "lab3user"
LAB3_KNOWN_PASSWORD = "Password123!"
LAB3_SRP_SALT = "lab3-srp-salt"
LAB4_TENANTS = ["ACME_1", "company_2"]

cognito_idp = boto3.client("cognito-idp", **AWS_CONFIG)
s3 = boto3.client("s3", **AWS_CONFIG)
iam = boto3.client("iam", **AWS_CONFIG)

LAB2_USER_POOL_ID = None
LAB2_CLIENT_ID = None
LAB3_USER_POOL_ID = None
LAB3_CLIENT_ID = None
LAB4_USER_POOL_ID = None
LAB4_CLIENT_ID = None



FLOCI_AVAILABLE = True
FLOCI_ERROR = None


def check_floci_available():
    global FLOCI_AVAILABLE, FLOCI_ERROR
    try:
        cognito_idp.list_user_pools(MaxResults=1)
        FLOCI_AVAILABLE = True
        FLOCI_ERROR = None
    except Exception as exc:
        FLOCI_AVAILABLE = False
        FLOCI_ERROR = str(exc)


def get_floci_warning():
    if FLOCI_AVAILABLE:
        return None
    return "Floci is not available on http://localhost:4566. Start it before using the labs."


def find_user_pool_id(pool_name):
    response = cognito_idp.list_user_pools(MaxResults=60)
    for pool in response.get("UserPools", []):
        if pool.get("Name") == pool_name:
            return pool.get("Id")
    return None


def get_or_create_user_pool(pool_name, schema=None):
    pool_id = find_user_pool_id(pool_name)
    if pool_id:
        return pool_id
    args = {"PoolName": pool_name}
    if schema:
        args["Schema"] = schema
    response = cognito_idp.create_user_pool(**args)
    return response["UserPool"]["Id"]


def find_user_pool_client_id(user_pool_id, client_name):
    response = cognito_idp.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
    for client in response.get("UserPoolClients", []):
        if client.get("ClientName") == client_name:
            return client.get("ClientId")
    return None


def get_or_create_user_pool_client(user_pool_id, client_name, explicit_auth_flows=None):
    client_id = find_user_pool_client_id(user_pool_id, client_name)
    if client_id:
        return client_id
    args = {"UserPoolId": user_pool_id, "ClientName": client_name}
    if explicit_auth_flows:
        args["ExplicitAuthFlows"] = explicit_auth_flows
    response = cognito_idp.create_user_pool_client(**args)
    return response["UserPoolClient"]["ClientId"]


def create_user_if_missing(user_pool_id, username, password, attributes):
    try:
        cognito_idp.admin_get_user(UserPoolId=user_pool_id, Username=username)
        return
    except Exception:
        pass

    cognito_idp.admin_create_user(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=attributes,
        MessageAction="SUPPRESS",
    )
    cognito_idp.admin_set_user_password(
        UserPoolId=user_pool_id, Username=username, Password=password, Permanent=True
    )


def init_lab1_identity_pool():
    try:
        s3.create_bucket(Bucket=LAB1_BUCKET_NAME)
    except Exception:
        pass

    s3.put_object(
        Bucket=LAB1_BUCKET_NAME,
        Key=LAB1_OBJECT_KEY,
        Body=FLAGS["lab1"],
    )

    role_name = "Lab1CognitoGuestRole"
    role_arn = None
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": "cognito-identity.amazonaws.com"},
                "Action": "sts:AssumeRoleWithWebIdentity",
            }
        ],
    }
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
        )
        role_arn = response["Role"]["Arn"]
    except Exception:
        try:
            response = iam.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
        except Exception:
            role_arn = None

    if role_arn:
        policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:ListAllMyBuckets", "s3:ListBucket"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": f"arn:aws:s3:::{LAB1_BUCKET_NAME}/*",
                },
            ],
        }
        try:
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName="Lab1S3ReadPolicy",
                PolicyDocument=json.dumps(policy_doc),
            )
            cognito_identity.set_identity_pool_roles(
                IdentityPoolId=LAB1_IDENTITY_POOL_ID,
                Roles={"unauthenticated": role_arn},
            )
        except Exception:
            pass


def init_lab2_self_signup():
    global LAB2_USER_POOL_ID, LAB2_CLIENT_ID
    LAB2_USER_POOL_ID = get_or_create_user_pool("Lab2SelfSignupPool")
    LAB2_CLIENT_ID = get_or_create_user_pool_client(
        LAB2_USER_POOL_ID,
        "Lab2SelfSignupClient",
        ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )


def init_lab3_auth_flow():
    global LAB3_USER_POOL_ID, LAB3_CLIENT_ID
    LAB3_USER_POOL_ID = get_or_create_user_pool("Lab3AuthFlowPool")
    LAB3_CLIENT_ID = get_or_create_user_pool_client(
        LAB3_USER_POOL_ID,
        "Lab3AuthFlowClient",
        [
            "ALLOW_USER_SRP_AUTH",
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
        ],
    )
    create_user_if_missing(
        LAB3_USER_POOL_ID,
        LAB3_KNOWN_USER,
        LAB3_KNOWN_PASSWORD,
        [
            {"Name": "email", "Value": "lab3user@example.com"},
            {"Name": "email_verified", "Value": "true"},
        ],
    )


def init_lab4_multitenant():
    global LAB4_USER_POOL_ID, LAB4_CLIENT_ID
    schema = [
        {
            "Name": "role",
            "AttributeDataType": "String",
            "Mutable": True,
            "Required": False,
        },
        {
            "Name": "tenant",
            "AttributeDataType": "String",
            "Mutable": True,
            "Required": False,
        },
    ]
    LAB4_USER_POOL_ID = get_or_create_user_pool("Lab4MultiTenantPool", schema)
    LAB4_CLIENT_ID = get_or_create_user_pool_client(
        LAB4_USER_POOL_ID,
        "Lab4MultiTenantClient",
        ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )

    create_user_if_missing(
        LAB4_USER_POOL_ID,
        "admin",
        "123",
        [
            {"Name": "email", "Value": "admin@empresa.com"},
            {"Name": "email_verified", "Value": "false"},
            {"Name": "custom:role", "Value": "admin"},
            {"Name": "custom:tenant", "Value": "ACME_1"},
        ],
    )
    create_user_if_missing(
        LAB4_USER_POOL_ID,
        "user",
        "123",
        [
            {"Name": "email", "Value": "user@empresa.com"},
            {"Name": "email_verified", "Value": "false"},
            {"Name": "custom:role", "Value": "user"},
            {"Name": "custom:tenant", "Value": "ACME_1"},
        ],
    )


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        page_title="Cognito Labs",
        floci_warning=get_floci_warning(),
    )


@app.route("/api/validate-flag", methods=["POST"])
def validate_flag():
    payload = request.get_json(silent=True) or {}
    lab = payload.get("lab", "").strip()
    value = payload.get("value", "").strip()
    if lab not in FLAGS:
        return jsonify({"error": "Unknown lab."}), 400
    return jsonify({"lab": lab, "ok": value == FLAGS[lab]})


@app.route("/lab1")
def lab1():
    return render_template(
        "lab1.html",
        page_title="Lab 1 - Guest Identity",
        floci_warning=get_floci_warning(),
        identity_pool_id=LAB1_IDENTITY_POOL_ID,
        bucket_name=LAB1_BUCKET_NAME,
        object_key=LAB1_OBJECT_KEY,
        region=AWS_CONFIG["region_name"],
        endpoint_url=AWS_CONFIG["endpoint_url"],
    )


def _lab1_validate_command(command, required_substrings, identity_id=None):
    if not command:
        return "Command is required."
    normalized = " ".join(command.strip().split())
    for token in required_substrings:
        if token not in normalized:
            return f"Missing required token: {token}"
    if LAB1_IDENTITY_POOL_ID not in normalized:
        return "Identity pool id is missing or incorrect."
    if identity_id and identity_id not in normalized:
        return "Identity id is missing or incorrect."
    return None


@app.route("/lab1/cli/get-id", methods=["POST"])
def lab1_cli_get_id():
    command = request.form.get("command", "")
    error = _lab1_validate_command(
        command,
        ["aws cognito-identity get-id", "--identity-pool-id"],
    )
    if error:
        return jsonify({"error": error}), 400

    identity_id = f"{AWS_CONFIG['region_name']}:{uuid.uuid4()}"
    resp = jsonify({"IdentityId": identity_id})
    resp.set_cookie("lab1_identity_id", identity_id)
    return resp


@app.route("/lab1/cli/get-credentials", methods=["POST"])
def lab1_cli_get_credentials():
    command = request.form.get("command", "")
    identity_id = request.cookies.get("lab1_identity_id")
    error = _lab1_validate_command(
        command,
        ["aws cognito-identity get-credentials-for-identity", "--identity-id"],
        identity_id=identity_id,
    )
    if error:
        return jsonify({"error": error}), 400
    if not identity_id:
        return jsonify({"error": "Identity id not found. Run get-id first."}), 400

    return jsonify(
        {
            "IdentityId": identity_id,
            "Credentials": {
                "AccessKeyId": "ASIA" + uuid.uuid4().hex[:16].upper(),
                "SecretAccessKey": uuid.uuid4().hex + uuid.uuid4().hex,
                "SessionToken": uuid.uuid4().hex + uuid.uuid4().hex,
                "Expiration": "2026-12-31T23:59:59Z",
            },
            "Flag": FLAGS["lab1"],
        }
    )


@app.route("/lab2", methods=["GET"])
def lab2():
    token = request.cookies.get("lab2_access_token")
    if token:
        try:
            cognito_idp.get_user(AccessToken=token)
            return render_template(
                "lab2.html",
                page_title="Lab 2 - Self Sign-Up",
                floci_warning=get_floci_warning(),
                client_id=LAB2_CLIENT_ID,
                flag=FLAGS["lab2"],
                show_flag=True,
            )
        except Exception:
            resp = make_response(redirect(url_for("lab2")))
            resp.delete_cookie("lab2_access_token")
            return resp

    return render_template(
        "lab2.html",
        page_title="Lab 2 - Self Sign-Up",
        floci_warning=get_floci_warning(),
        client_id=LAB2_CLIENT_ID,
        show_flag=False,
    )


@app.route("/lab2/login", methods=["POST"])
def lab2_login():
    username = request.form.get("username")
    password = request.form.get("password")
    try:
        response = cognito_idp.initiate_auth(
            ClientId=LAB2_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        token = response["AuthenticationResult"]["AccessToken"]
        resp = make_response(redirect(url_for("lab2")))
        resp.set_cookie("lab2_access_token", token)
        return resp
    except cognito_idp.exceptions.UserNotConfirmedException:
        try:
            cognito_idp.admin_confirm_sign_up(UserPoolId=LAB2_USER_POOL_ID, Username=username)
            response = cognito_idp.initiate_auth(
                ClientId=LAB2_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
            token = response["AuthenticationResult"]["AccessToken"]
            resp = make_response(redirect(url_for("lab2")))
            resp.set_cookie("lab2_access_token", token)
            return resp
        except Exception as exc:
            return render_template(
                "lab2.html",
                page_title="Lab 2 - Self Sign-Up",
                floci_warning=get_floci_warning(),
                client_id=LAB2_CLIENT_ID,
                show_flag=False,
                err=f"Authentication Failure: {exc}",
            )
    except Exception as exc:
        return render_template(
            "lab2.html",
            page_title="Lab 2 - Self Sign-Up",
            floci_warning=get_floci_warning(),
            client_id=LAB2_CLIENT_ID,
            show_flag=False,
            err=f"Authentication Failure: {exc}",
        )


@app.route("/lab3", methods=["GET"])
def lab3():
    return render_template(
        "lab3.html",
        page_title="Lab 3 - Auth Flow",
        floci_warning=get_floci_warning(),
        client_id=LAB3_CLIENT_ID,
        known_user=LAB3_KNOWN_USER,
        known_password=LAB3_KNOWN_PASSWORD,
        srp_salt=LAB3_SRP_SALT,
        show_flag=False,
    )


@app.route("/lab3/srp-init", methods=["POST"])
def lab3_srp_init():
    username = request.form.get("username", "").strip()
    if not username:
        return jsonify({"error": "Username is required."}), 400
    if username != LAB3_KNOWN_USER:
        return jsonify({"error": "Unknown user for SRP."}), 400

    challenge_id = uuid.uuid4().hex
    response = {
        "ChallengeName": "PASSWORD_VERIFIER",
        "ChallengeParameters": {
            "USER_ID_FOR_SRP": username,
            "SALT": uuid.uuid4().hex,
            "SRP_B": uuid.uuid4().hex,
            "SECRET_BLOCK": uuid.uuid4().hex,
        },
        "Session": challenge_id,
    }
    resp = jsonify(response)
    resp.set_cookie("lab3_srp_session", challenge_id)
    return resp


@app.route("/lab3/srp-verify", methods=["POST"])
def lab3_srp_verify():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    session = request.form.get("session", "").strip()
    expected_session = request.cookies.get("lab3_srp_session")

    if not username or not password or not session:
        return jsonify({"error": "Username, password, and session are required."}), 400
    if session != expected_session:
        return jsonify({"error": "Invalid SRP session. Run SRP init first."}), 400
    if username != LAB3_KNOWN_USER or password != LAB3_KNOWN_PASSWORD:
        return jsonify({"error": "Invalid SRP credentials."}), 401

    return jsonify(
        {
            "AuthenticationResult": {
                "AccessToken": "SRP_SIMULATED_TOKEN",
                "IdToken": "SRP_SIMULATED_ID_TOKEN",
                "TokenType": "Bearer",
                "ExpiresIn": 3600,
            },
            "Note": "SRP flow simulated. Flag requires USER_PASSWORD_AUTH misconfiguration.",
        }
    )


@app.route("/lab3/login", methods=["POST"])
def lab3_login():
    username = request.form.get("username")
    password = request.form.get("password")
    auth_flow = request.form.get("auth_flow", "USER_SRP_AUTH")

    if auth_flow != "USER_PASSWORD_AUTH":
        expected = hashlib.sha256(
            f"{LAB3_KNOWN_USER}:{LAB3_KNOWN_PASSWORD}:{LAB3_SRP_SALT}".encode("utf-8")
        ).hexdigest()
        if username != LAB3_KNOWN_USER or password != expected:
            return render_template(
                "lab3.html",
                page_title="Lab 3 - Auth Flow",
                floci_warning=get_floci_warning(),
                client_id=LAB3_CLIENT_ID,
                known_user=LAB3_KNOWN_USER,
                known_password=LAB3_KNOWN_PASSWORD,
                srp_salt=LAB3_SRP_SALT,
                show_flag=False,
                err="SRP simulator rejected the checksum. Check username and password.",
            )
        return render_template(
            "lab3.html",
            page_title="Lab 3 - Auth Flow",
            floci_warning=get_floci_warning(),
            client_id=LAB3_CLIENT_ID,
            known_user=LAB3_KNOWN_USER,
            known_password=LAB3_KNOWN_PASSWORD,
            srp_salt=LAB3_SRP_SALT,
            show_flag=False,
            srp_message="SRP simulated successfully. To obtain the flag, force USER_PASSWORD_AUTH with a clear password.",
        )

    try:
        cognito_idp.initiate_auth(
            ClientId=LAB3_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        return render_template(
            "lab3.html",
            page_title="Lab 3 - Auth Flow",
            floci_warning=get_floci_warning(),
            client_id=LAB3_CLIENT_ID,
            known_user=LAB3_KNOWN_USER,
            known_password=LAB3_KNOWN_PASSWORD,
            srp_salt=LAB3_SRP_SALT,
            show_flag=True,
            flag=FLAGS["lab3"],
        )
    except Exception as exc:
        return render_template(
            "lab3.html",
            page_title="Lab 3 - Auth Flow",
            floci_warning=get_floci_warning(),
            client_id=LAB3_CLIENT_ID,
            known_user=LAB3_KNOWN_USER,
            known_password=LAB3_KNOWN_PASSWORD,
            srp_salt=LAB3_SRP_SALT,
            show_flag=False,
            err=f"Authentication Failure: {exc}",
        )


@app.route("/lab4")
def lab4_gateway():
    return render_template(
        "lab4_gateway.html",
        page_title="Lab 4 - Multi-Tenant",
        floci_warning=get_floci_warning(),
        tenants=LAB4_TENANTS,
    )


@app.route("/lab4/register", methods=["GET", "POST"])
def lab4_register():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        email = request.form.get("email").strip()
        tenant = request.form.get("tenant").strip()
        try:
            cognito_idp.sign_up(
                ClientId=LAB4_CLIENT_ID,
                Username=username,
                Password=password,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "custom:role", "Value": "user"},
                    {"Name": "custom:tenant", "Value": tenant},
                ],
            )
            cognito_idp.admin_confirm_sign_up(UserPoolId=LAB4_USER_POOL_ID, Username=username)
            return render_template(
                "lab4_register.html",
                page_title="Lab 4 - Register",
                floci_warning=get_floci_warning(),
                success=True,
            )
        except Exception as exc:
            return render_template(
                "lab4_register.html",
                page_title="Lab 4 - Register",
                floci_warning=get_floci_warning(),
                err=str(exc),
                success=False,
                tenants=LAB4_TENANTS,
            )

    return render_template(
        "lab4_register.html",
        page_title="Lab 4 - Register",
        floci_warning=get_floci_warning(),
        success=False,
        tenants=LAB4_TENANTS,
    )


@app.route("/lab4/login/<tenant_name>", methods=["GET", "POST"])
def lab4_login(tenant_name):
    if tenant_name not in LAB4_TENANTS:
        return redirect(url_for("lab4_gateway"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        try:
            response = cognito_idp.initiate_auth(
                ClientId=LAB4_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
            jwt_token = response["AuthenticationResult"]["AccessToken"]

            user_info = cognito_idp.get_user(AccessToken=jwt_token)
            attributes = {attr["Name"]: attr["Value"] for attr in user_info["UserAttributes"]}
            user_assigned_tenant = attributes.get("custom:tenant")
            if user_assigned_tenant != tenant_name:
                return render_template(
                    "lab4_login.html",
                    page_title="Lab 4 - Login",
                    floci_warning=get_floci_warning(),
                    tenant_name=tenant_name,
                    err=(
                        "Access Denied: Your identity is registered under "
                        f"'{user_assigned_tenant}', not allowed inside '{tenant_name}'."
                    ),
                )

            resp = make_response(redirect(url_for("lab4_dashboard")))
            resp.set_cookie("lab4_access_token", jwt_token)
            return resp
        except Exception as exc:
            return render_template(
                "lab4_login.html",
                page_title="Lab 4 - Login",
                floci_warning=get_floci_warning(),
                tenant_name=tenant_name,
                err=f"Authentication Failure: {exc}",
            )

    return render_template(
        "lab4_login.html",
        page_title="Lab 4 - Login",
        floci_warning=get_floci_warning(),
        tenant_name=tenant_name,
    )


@app.route("/lab4/dashboard")
def lab4_dashboard():
    token = request.cookies.get("lab4_access_token")
    if not token:
        return redirect(url_for("lab4_gateway"))

    try:
        user_info = cognito_idp.get_user(AccessToken=token)
        attributes = {attr["Name"]: attr["Value"] for attr in user_info["UserAttributes"]}

        user_sub = attributes.get("sub")
        user_email = attributes.get("email")
        email_verified = attributes.get("email_verified", "false")
        role_in_cognito = attributes.get("custom:role", "user")
        tenant_in_cognito = attributes.get("custom:tenant", "unknown")

        badge_class = "badge-user" if role_in_cognito == "user" else "badge-admin"
        show_flag = tenant_in_cognito == "company_2" and role_in_cognito == "admin"

        return render_template(
            "lab4_dashboard.html",
            page_title="Lab 4 - Multi-Tenant",
            floci_warning=get_floci_warning(),
            user_sub=user_sub,
            user_email=user_email,
            email_verified=email_verified,
            role_in_cognito=role_in_cognito,
            tenant_in_cognito=tenant_in_cognito,
            badge_class=badge_class,
            token=token,
            show_flag=show_flag,
            flag=FLAGS["lab4"],
            endpoint_url=AWS_CONFIG["endpoint_url"],
            region=AWS_CONFIG["region_name"],
        )
    except Exception:
        resp = make_response(redirect(url_for("lab4_gateway")))
        resp.delete_cookie("lab4_access_token")
        return resp


@app.route("/lab4/logout")
def lab4_logout():
    resp = make_response(redirect(url_for("lab4_gateway")))
    resp.delete_cookie("lab4_access_token")
    return resp


if __name__ == "__main__":
    check_floci_available()
    if FLOCI_AVAILABLE:
        init_lab1_identity_pool()
        init_lab2_self_signup()
        init_lab3_auth_flow()
        init_lab4_multitenant()
    else:
        print("Floci is not available. Start Floci on http://localhost:4566 and restart the app.")

    app.run(host="0.0.0.0", port=5001)
