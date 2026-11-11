# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: open the
repository's **Security** tab and choose **Report a vulnerability**
(GitHub private vulnerability reporting). Do not open a public issue,
discussion, or pull request for a security problem.

Please include:

- what the issue is and what an attacker could do with it,
- steps or a proof of concept to reproduce it,
- the affected version (commit SHA) and configuration.

You should get an acknowledgement within a few days. Once the issue is
confirmed, we will work on a fix and agree with you on a disclosure date. We
credit reporters in the advisory unless you prefer not to be named.

## Supported versions

This is a template you copy into your own project, so fixes land on `main`
only. If you have built on an earlier copy, watch the repository's security
advisories and port the relevant fixes into your project.

## Scope

In scope: the code in this repository (backend, frontend, mobile, the deploy
scripts and workflows) used as documented.

Out of scope: vulnerabilities in a deployment that changed the security
defaults (for example a weak `SECRET_KEY`, `ENVIRONMENT` not set to
`production`, or debug settings left on in production), and issues in
third-party services or dependencies that are not caused by how this
repository uses them. Please report those upstream.
