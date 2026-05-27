# aws-cognito-lab
Multi-lab Cognito playground for AWS CLI abuse and auth misconfiguration. The app serves a dashboard with four labs and a per-lab flag validator.

This lab uses [Floci](https://floci.io/#quickstart) to emulate AWS Cognito and AWS services.

```bash
docker run -d -p 4566:4566 --name floci-aws floci/floci
```

It is recommended to use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate

pip install boto3
pip install flask

python3 app.py
```

Open the dashboard at http://localhost:5001.

## Labs

1. **Lab 1 - Guest Identity Pool + S3 (CLI Simulator)**
  - Floci does not implement `cognito-identity`, so this lab emulates the CLI flow in the browser.
  - Use the on-page CLI simulator to get an identity id and then credentials to reveal the flag.

2. **Lab 2 - Self Sign-Up Abuse**
  - UI only allows login, but the Client ID is exposed.
  - Use `aws cognito-idp sign-up` via CLI, then login in the web UI to reveal the flag.
  - If the user is not confirmed, the app auto-confirms on first login (Floci has no email delivery).

3. **Lab 3 - Auth Flow Variation**
  - The UI simulates SRP: the password is hashed client-side and sent as a checksum.
  - Intercept the request and change `auth_flow` to `USER_PASSWORD_AUTH` and send the clear password to get the flag.

4. **Lab 4 - Multi-Tenant Escalation**
  - JWT token can be used to change tenant + role via AWS CLI.
  - Flag appears only when `custom:tenant=company_2` and `custom:role=admin`.

## Notes

- The app checks if Floci is reachable on startup and warns if it is not.
- Flags are validated individually (correct/incorrect) on the dashboard.
- Lab 1 uses a built-in CLI simulator because Floci does not support `cognito-identity`.
- CLI commands for each lab are shown inside the lab pages.
