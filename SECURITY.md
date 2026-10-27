# Security policy

## Supported versions

Security fixes are made on `main` and released in the next version. Only the newest release
receives them; an older release is not patched. Upgrade to the newest release before reporting,
and say in the report if you cannot.

| Version | Security fixes |
| --- | --- |
| Newest release on [GitHub Releases](https://github.com/SeQuSoS-Project/QRosetta/releases) | Yes |
| Any older release, including `v1.0.0` | No |

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting: open the repository's
**Security** tab and choose **Report a vulnerability**, or go to
<https://github.com/SeQuSoS-Project/QRosetta/security/advisories/new>. Only the maintainers and you
can read the report, and a fix and an advisory can be prepared in the same place.

If you cannot use GitHub, email Majid Haghparast at
[majid.m.haghparast@jyu.fi](mailto:majid.m.haghparast@jyu.fi) with "QRosetta security" in the
subject.

Do not open a public issue, discussion or pull request for a vulnerability.

Include:

- the version (`qrosetta version --json`, or the commit of a source checkout) and whether you ran
  the local stack (`./qrosetta start`) or a shared server (`EXECUTION_MODE=kubernetes`);
- the component: the API, the web page, the `qrosetta` command, a runner or compiler image, or the
  deployment files;
- the steps, request or circuit that shows the problem, and what an attacker gains.

Never put secrets in a report, an issue or an attachment: no passwords, `SECRET_KEY`, access
tokens, share-link tokens, the lifecycle token, `.env` files, database URLs or S3 keys. If a
secret of yours was exposed, revoke or rotate it first; a share link can be revoked from the
Circuits tab of the saved run. If the problem is that QRosetta leaks a secret, describe where it
appears and replace the value with `<redacted>`.

## Behaviour that is not a vulnerability

These are documented choices; a report that one of them can be bypassed is welcome.

- The local stack trusts its own machine. nginx is published on `127.0.0.1:8080`, and in local
  mode any client may set `bypass_limits`. Publishing it on other interfaces
  (`QROSETTA_HTTP_BIND`) is the operator's choice.
- A job id works like a password: anyone who holds it can read the job's results until the job
  expires, and can save the job to their account when it was submitted without signing in.
- Simulator results that disagree with each other, or with the expected state, are correctness
  issues. Open a normal issue for them (see `SUPPORT.md`), or report them to the SDK's own
  project when the cause is upstream.
