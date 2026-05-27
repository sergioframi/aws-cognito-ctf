# Solutions

This document explains the intended solution path for each lab.

## Lab 1 - Guest Identity Pool + S3 (CLI Simulator)

**Goal:** emulate the Cognito Identity flow in Floci and obtain the flag.

**Why:** Floci does not implement `cognito-identity`, so the lab simulates the workflow in the browser.

**Steps:**
1. Open Lab 1 and use the **CLI Simulator**.
2. Run **Step 1 (get-id)** to receive an `IdentityId`.
3. The app auto-fills **Step 2 (get-credentials-for-identity)** with that `IdentityId`.
4. Run **Step 2** to receive the credentials payload and the flag.

## Lab 2 - Self Sign-Up Abuse

**Goal:** create a user even though the UI only shows login.

**Steps:**
1. Copy the exposed `ClientId` from the Lab 2 page.
2. Run the CLI sign-up:
   ```bash
   aws cognito-idp sign-up \
     --client-id <CLIENT_ID> \
     --username demo-user \
     --password 'Password123!' \
     --user-attributes Name=email,Value=demo-user@example.com \
     --endpoint-url http://localhost:4566 \
     --region us-east-1
   ```
3. Login in the web UI with the new user.
4. If the account is not confirmed, the app auto-confirms on the first login (Floci does not send emails).
5. The flag appears after successful login.

## Lab 3 - Auth Flow Variation (SRP Simulated)

**Goal:** bypass the SRP flow by forcing `USER_PASSWORD_AUTH`.

**How it works:**
- The UI uses `USER_SRP_AUTH` by default and hashes the password client-side (SRP checksum).
- The backend accepts `USER_PASSWORD_AUTH` and will return the flag if you send the password in clear text.

**Steps:**
1. Attempt login normally; the SRP simulator accepts the checksum but does not show the flag.
2. Intercept the request and change:
   - `auth_flow` to `USER_PASSWORD_AUTH`
   - `password` to the clear text password
3. Submit the modified request to get the flag.

## Lab 4 - Multi-Tenant Escalation

**Goal:** switch tenant and role using the JWT token.

**Steps:**
1. Login with `admin/123` or `user/123`.
2. Copy the access token from the dashboard.
3. Update attributes via CLI:
   ```bash
   aws cognito-idp update-user-attributes \
     --access-token "<TOKEN>" \
     --user-attributes Name="custom:tenant",Value="company_2" Name="custom:role",Value="admin" \
     --endpoint-url http://localhost:4566 \
     --region us-east-1
   ```
4. Refresh the dashboard to see the flag.
