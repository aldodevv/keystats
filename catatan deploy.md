Settings
Table of contents
[General](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#general)
[Build](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#build)
[Deploy](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#deploy)
[Custom Domains](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#custom-domains)
[PR Previews](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#pr-previews)
[Networking](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#networking)
[Edge Caching](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#edge-caching)
[Notifications](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#notifications)
[Health Checks](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#health-checks)
[Maintenance Mode](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#maintenance-mode)
[Delete or suspend](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/settings#delete-or-suspend)
General
Name
A unique name for your Web Service.
Edit
Region
Your services in the same [region](https://render.com/docs/regions) can communicate over a [private network.](https://render.com/docs/private-network)
Instance Type
Instance Type is now [Compute Plan](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/compute). Read the [announcement](https://render.com/blog/new-compute-plans-for-memory-intensive-applications).
See [remaining free usage](https://dashboard.render.com/billing#free-usage), or learn about [free service limits](https://render.com/docs/free).
Build
Source
The build source for your Web Service
[aldodevv / keystatsengine](https://github.com/aldodevv/keystatsengine)
Edit
Branch
The Git branch to build and deploy.
Branch
Edit
Root DirectoryOptional
If set, Render runs commands from this directory instead of the repository root. Additionally, code changes outside of this directory do not trigger an auto-deploy. Most commonly used with a [monorepo.](https://render.com/docs/monorepo-support#setting-a-root-directory)
Edit
Build Command
Render runs this command to build your app before each deploy.
$
Edit
Git Credentials
User providing the credentials to pull the repository.
Use My Credentials
Build Filters
Include or ignore specific paths in your repo when determining whether to trigger an auto-deploy. Paths are relative to your repo's root directory. [Learn more.](https://render.com/docs/monorepo-support#setting-build-filters)
Edit
Included Paths
Changes that match these paths will trigger a new build.
Add Included Path
Ignored Paths
Changes that match these paths will not trigger a new build.
Add Ignored Path
Deploy
Pre-Deploy CommandOptional
Render runs this command before the start command. Useful for database migrations and static asset uploads.
Edit
Start Command
Render runs this command to start your app with each deploy.
$
Edit
Auto-Deploy
By default, Render automatically deploys your service whenever you update its code or configuration. Disable to handle deploys manually. [Learn more.](https://render.com/docs/deploys#automatic-deploys)
autoDeployTriggerOn Commit
Edit
Deploy Hook
Your private URL to trigger a deploy for this server. Remember to keep this a secret.
Regenerate hook
Loading...
PR Previews
Pull Request Previews
Spin up temporary instances to test pull requests opened against the main branch of aldodevv/keystatsengine. Choose Automatic to preview all PRs, or Manual for only PRs with [render preview] in their title. [Pull Request Previews](https://render.com/docs/service-previews#pull-request-previews-git-backed) create a new instance for just this service. Use [Preview Environments](https://render.com/docs/preview-environments) to clone a group of services for every PR.
prPreviewsEnabledOff
Edit
Networking
Edge Caching
Serve static content at the edge to improve performance and reduce service load. [Learn more.](https://render.com/docs/web-service-caching)
PaidEdge Caching is only available for paid instances.[Upgrade](https://dashboard.render.com/web/srv-da60chqjobas7384so7g/plan)
Notifications
Service Notifications
Set notifications to receive for your service. This setting will override your workspace's default settings.
notificationsToSendUse workspace default (Only failure notifications)
Edit
Preview Environment Notifications
Configure notifications for [preview environments](https://render.com/docs/preview-environments) and [service previews.](https://render.com/docs/service-previews)
previewNotificationsEnabledUse account default (Disabled)
Edit
Health Checks
Health Check Path
Provide an HTTP endpoint path that Render messages periodically to monitor your service. [Learn More.](https://render.com/docs/health-checks)
Edit
Maintenance Mode
PaidMaintenance mode is only available for paid instances.

env 
TELEGRAM_BOT_TOKEN = 8653878371:AAGgLIDflVM2MxGU9omMcWbzqKT7MyQ_olo
TELEGRAM_CHAT_ID = 7690577065