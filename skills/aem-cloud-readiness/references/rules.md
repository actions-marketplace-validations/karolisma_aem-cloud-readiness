# Cloud Service blocker catalogue

Rules for auditing an AEM 6.x codebase before a move to AEM as a Cloud Service (AEMaaCS).

**Version:** v0.2, researched against Adobe's documentation on 15 November 2026.

## How to read a rule

Each rule has these fields:

- **Impact:** what happens in practice on AEMaaCS. This is the catalogue's own judgment: `Blocker` (stops the pipeline or the feature can't work), `High` (must be fixed before go-live), `Medium` (rework needed, timing flexible), `Low` (advisory).
- **Adobe rule:** the matching Cloud Manager code-quality rule, with Adobe's type and severity from the [AEMaaCS Custom Code Quality Rules page][cqr], or the Build Analyzer check. `None` means Adobe has no rule for it.
- **Evidence:** `Documented` means Adobe's docs state the constraint. `Inferred` means it follows from the docs or from field experience, but no Adobe page says it outright. Say so in the report.
- **Adobe skill:** the pattern in [Adobe's AEM Cloud Migration skill][skill] that can fix the finding, if one exists.
- **Scanner:** what `scripts/scan.py` flags. Every scanner signal is a heuristic, not Adobe text.

Two things to keep in mind:

- **Adobe's severities understate impact.** Most Cloud Service compatibility rules are `Minor` code smells, so the quality step passes code whose feature no longer exists (Classic UI, custom run modes, reverse replication). That's why Impact and Adobe rule are separate fields.
- **Use the AEMaaCS rules page, not the Cloud Manager (AMS) one.** They list different severities for the same rules.

## Deprecated-API deadline

Adobe is enforcing API removals on a schedule ([Deprecated and Removed Features][dep]):

| When | What happens |
| --- | --- |
| November 2026 | Notification emails start |
| December 2026 | Pipelines using affected APIs pause at Code Quality (can be overridden) |
| January 2027 | Those pipelines fail |
| 31 March 2027 | First batch of libraries is removed |
| 31 December 2027 | Second batch (mostly marked tentative) |

Rules 011–013 cover this. Check the dates against the live page before quoting them to a client.

---

# Packages and configuration

## AEMCS-001: Mutable and immutable content in one package
- **Impact:** High
- **Adobe rule:** `ImmutableMutableMixedPackage` (Code Smell, Minor)
- **Evidence:** Documented. That the build fails (through the FileVault package-type validator) is inferred.
- **Adobe skill:** none
- **Scanner:** a `filter.xml` with roots under `/apps` **and** under `/content`, `/conf`, `/etc`, `/var`, `/home`, `/system` or `/tmp`.

**Why:** `/apps` is immutable at runtime and ships in the image. Mutable content is installed separately, so one package can't deploy to both.

**Note:** `/oak:index` is not a finding here. Index definitions ship **with the code package** (`ui.apps`), so `/apps` plus `/oak:index` is correct. `/libs` is covered by AEMCS-018.

**Fix:** split into `ui.apps` (code), `ui.content` (mutable content) and `ui.config` (OSGi configs), embedded in an `all` container package. See [AEM Project Structure][structure].

## AEMCS-002: OSGi configuration in a superseded format
- **Impact:** Low (advisory)
- **Adobe rule:** None
- **Evidence:** Documented. Adobe calls `.config`, `.cfg` and `sling:OsgiConfig` XML "superseded" by `.cfg.json`. It doesn't call them unsupported.
- **Adobe skill:** `osgi-cloud-manager`
- **Scanner:** `sling:OsgiConfig` nodes, `.config` and `.cfg` files in `config*` folders.

**Fix:** convert to `<PID>.cfg.json` (or `<factoryPID>~<name>.cfg.json`). Use `$[env:NAME]`, `$[secret:NAME]` or `$[env:NAME;default=value]` for values that differ per environment. Adobe prefers inline values in Git for Stage and Production unless the value is a secret. See [Configuring OSGi][osgi].

## AEMCS-003: Unsupported run modes
- **Impact:** High
- **Adobe rule:** `SupportedRunmode` (Code Smell, Minor)
- **Evidence:** Documented that custom run modes aren't possible. What happens to the folder at runtime is not documented.
- **Adobe skill:** `osgi-cloud-manager` (flags them)
- **Scanner:** any `config.<x>` folder outside the 15 supported names.

**Supported folders:** `config`, `config.author`, `config.publish`, `config.dev`, `config.rde`, `config.stage`, `config.prod`, and `author` or `publish` combined with `dev`, `rde`, `stage` or `prod`. The service comes first: `config.author.dev`, never `config.dev.author`. There is no `config.preview`. Preview uses the publish configuration.

**Fix:** fold custom environments (`uat`, `qa`, `local`…) into the supported ones, and use environment variables for values that differ. See [Deploying to AEMaaCS][deploy].

## AEMCS-018: Content under /libs
- **Impact:** Blocker
- **Adobe rule:** `BannedPath` (Bug, Critical)
- **Evidence:** Documented
- **Adobe skill:** none
- **Scanner:** a filter root under `/libs`, or a `jcr_root/libs` folder.

**Fix:** move overlays to `/apps`. Never deploy to `/libs`.

## AEMCS-014: Uber-jar dependency
- **Impact:** High
- **Adobe rule:** None
- **Evidence:** Documented that the API jar is now `com.adobe.aem:aem-sdk-api`. That uber-jar is "unsupported" is not stated in so many words.
- **Adobe skill:** none
- **Scanner:** `uber-jar` in a `pom.xml`.

**Fix:** depend on `com.adobe.aem:aem-sdk-api` (scope `provided`) and add the `aemanalyser-maven-plugin`, which checks the build locally the way Cloud Manager does. See [AEM SDK][sdk].

## AEMCS-015: Java version for the build
- **Impact:** High
- **Adobe rule:** None
- **Evidence:** Documented. The runtime is Java 21. Builds can target 11, 17 or 21, and `.cloudmanager/java-version` selects JDK 17 or 21 for the build.
- **Adobe skill:** none
- **Scanner:** a Maven project with no `.cloudmanager/java-version`, or a value other than `17` or `21`.

**Fix:** add `.cloudmanager/java-version` and update the compiler and plugin versions. See [Build Environment][build].

## AEMCS-020: Custom log files and logging frameworks
- **Impact:** High
- **Adobe rule:** Build Analyzer `configuration-api`
- **Evidence:** Documented. AEMaaCS writes Java logs to `logs/error.log` only. The `file` and `pattern` properties of logger configs have been ignored since 31 August 2025.
- **Adobe skill:** none
- **Scanner:** Sling logger factory configs with a `org.apache.sling.commons.log.file` other than `logs/error.log`, writer configs, and `logback.xml` files.

**Fix:** log everything to `logs/error.log` at the right level. For Splunk, Datadog and similar, declare log forwarding in `logForwarding.yaml` and deploy it with a config pipeline. See [custom log files][kblog] and [Log forwarding][logfwd].

---

# Java code

## AEMCS-004: Administrative sessions and resource resolvers
- **Impact:** Medium
- **Adobe rule:** None dedicated. May surface through the deprecated-API rules (`java:S1874`, `CQRules:AMSCORE-553`).
- **Evidence:** Inferred. These methods are deprecated and have been restricted by an allow-list since AEM 6.3, but no AEMaaCS page says they fail at runtime. Test on the Cloud SDK before calling it a blocker.
- **Adobe skill:** none
- **Scanner:** `loginAdministrative(`, `getAdministrativeResourceResolver(`, `getAdministrativeSession(`.

**Fix:** create a service user with least-privilege ACLs through repoinit, map it with a `ServiceUserMapperImpl.amended` config, and call `getServiceResourceResolver()` with the subservice name.

## AEMCS-005: Replication agents and the Replication API
- **Impact:** High for custom or reverse agents. Low for plain `Replicator.replicate()` calls.
- **Adobe rule:** `ReverseReplication` (Code Smell, Minor), for reverse agents only
- **Evidence:** Documented that AEMaaCS uses Sling Content Distribution and that custom agents aren't supported. That `AgentManager` or `ReplicationQueue` code breaks is inferred.
- **Adobe skill:** `replication`
- **Scanner:** agent configs under `/etc/replication`, and `com.day.cq.replication` classes (`Replicator`, `AgentManager`, `Agent`, `ReplicationQueue`) in Java.

**What to check:**
- **Agent configs** under `/etc/replication` are always a finding. Only `publish` and `preview` exist.
- **Plain `Replicator.replicate()`** is supported. Check the limits: stay under 100 paths per call, 500 is the hard limit, and the payload ceiling is 10 MB.
- **Bulk or tree publishing code** should move to the Tree Activation workflow step.
- **Agent or queue introspection** needs redesign.

See [Replication][repl].

## AEMCS-022: Reverse replication
- **Impact:** High
- **Adobe rule:** `ReverseReplication` (Code Smell, Minor)
- **Evidence:** Documented. Publish-to-author replication isn't supported.
- **Adobe skill:** none
- **Scanner:** reverse agents or outbox settings in package content (`reverseReplication`, `rev-agent`, `/var/replication/outbox`).

**Fix:** store user-generated data in an external store or service, not on publish for later reverse replication. See [Development Guidelines][dev].

## AEMCS-007: Writing to the local filesystem
- **Impact:** Medium to High
- **Adobe rule:** None
- **Evidence:** Documented. The disk is ephemeral and goes away when instances are recycled.
- **Adobe skill:** `inputStream` (related stream handling)
- **Scanner:** `new FileOutputStream(`, `new FileWriter(`, `Files.write(`, `Files.newOutputStream(`, `File.createTempFile(`.

**What to check:** short-lived temp files inside one request are tolerated. Anything meant to persist, or to be shared between instances, is a finding. Also watch for `asset.getOriginal().getStream()` on large binaries.

**Fix:** keep persistent data in the repository or in external storage.

## AEMCS-011: API packages already removed
- **Impact:** Blocker
- **Adobe rule:** Build Analyzer import check (`api-regions-exportsimports`)
- **Evidence:** Documented that the packages are removed. That the build fails on them is inferred from how the analyser works.
- **Adobe skill:** `guavaCache` (Guava cache to Caffeine only)
- **Scanner:** imports of `com.google.common.` (Guava), `org.apache.abdera.`, `com.mongodb.`, `ch.qos.logback.`, `org.apache.log4j.`, `org.apache.felix.scr.`, `org.apache.felix.webconsole.`, `org.eclipse.jetty.`, `com.day.crx.`.

**Fix:** replace the API, or embed your own copy of the library in the bundle where licensing allows. See [Deprecated and Removed Features][dep].

## AEMCS-012: APIs removed on 31 March 2027
- **Impact:** Blocker from January 2027, when pipelines start failing
- **Adobe rule:** `java:S1874` (Info to Major, rising as removal nears)
- **Evidence:** Documented
- **Adobe skill:** none
- **Scanner:** imports of `org.bson.`, `com.github.jknack.handlebars.`, `com.day.cq.xss.`, `com.day.cq.wcm.commons.utils.`, `org.apache.tika.`, `org.apache.commons.fileupload.`, `opennlp.tools.`, `com.day.cq.commons.predicate.`.

**Fix:** move to the supported replacement (for example `org.apache.sling.xss` for XSS protection) before January 2027.

## AEMCS-013: APIs removed on 31 December 2027 (tentative)
- **Impact:** High
- **Adobe rule:** `java:S1874`; `CQRules:AMSCORE-553` (Code Smell, Minor)
- **Evidence:** Documented, with the date mostly marked tentative
- **Adobe skill:** none
- **Scanner:** imports of `org.apache.commons.lang.` (v2), `org.apache.commons.collections.` (v3), `org.json.`, `org.apache.sling.commons.json.`, `com.adobe.granite.xss.`, `org.osgi.service.http.`, `org.apache.sling.runmode.`.

**Fix:** plan the move to commons-lang3, commons-collections4, a supported JSON library and `org.apache.sling.xss`.

## AEMCS-016: HTTP clients without timeouts
- **Impact:** High
- **Adobe rule:** `CQRules:ConnectionTimeoutMechanism` (Bug, Critical)
- **Evidence:** Documented
- **Adobe skill:** none
- **Scanner:** `HttpClients.createDefault()` and `HttpClientBuilder.create().build()`. Confirm by checking for a `RequestConfig` with timeouts.

**Fix:** set explicit connect and read timeouts on every outgoing call. Adobe suggests 1 second to connect and 5 seconds to read. See [Development Guidelines][dev].

## AEMCS-017: Sling Commons Scheduler
- **Impact:** Medium
- **Adobe rule:** `CQRules:AMSCORE-554` (Code Smell, Minor)
- **Evidence:** Documented. Scheduled work isn't guaranteed to run, because instances can stop at any time.
- **Adobe skill:** `scheduler`
- **Scanner:** `org.apache.sling.commons.scheduler` imports and `scheduler.expression` properties.

**Fix:** use Sling Jobs for work that must complete, and make the job resumable.

## AEMCS-023: Native binaries and process execution
- **Impact:** Blocker
- **Adobe rule:** Build Analyzer `bundle-nativecode`
- **Evidence:** Documented
- **Adobe skill:** none
- **Scanner:** `Runtime.getRuntime().exec(`, `new ProcessBuilder(`, `System.loadLibrary(`.

**Fix:** move the work to an external service, for example Asset Compute workers for ImageMagick or FFmpeg-style processing.

---

# Content, indexes and authoring

## AEMCS-006: Custom Oak index naming and placement
- **Impact:** Medium
- **Adobe rule:** `IndexName`, `IndexValidFullyCustomName`, `OakIndexLocation` (Code Smell, Minor); `IndexNotUnderUIContent` (Improvement, Minor)
- **Evidence:** Documented naming patterns. What happens to a misnamed index is not documented.
- **Adobe skill:** `oakIndex` (beta)
- **Scanner:** `oak:QueryIndexDefinition` nodes whose name doesn't end in `-<productVersion>-custom-<customVersion>`.

**Naming patterns:**
- A customised product index: `<indexName>-<productVersion>-custom-<customVersion>`, for example `damAssetLucene-8-custom-4`.
- A fully custom index: `<prefix>.<indexName>-<productVersion>-custom-<customVersion>`, for example `acme.product-1-custom-3`.

**Placement:** definitions live in `ui.apps` under `_oak_index`, as direct children of `/oak:index`, with `allowIndexDefinitions` and `noIntermediateSaves` set to true in the FileVault plugin. See [Content Search and Indexing][index].

## AEMCS-019: Index properties that block the pipeline
- **Impact:** Blocker
- **Adobe rule:** `IndexType`, `IndexTikaNode`, `IndexAsyncProperty`, `IndexDamAssetLucene` (all Bug, Blocker)
- **Evidence:** Documented
- **Adobe skill:** `oakIndex` (beta)
- **Scanner:** index definitions whose `type` isn't `lucene`, or whose `async` is missing or not one of `[async]`, `[async,nrt]`, `[fulltext-async]`. The scanner doesn't check the `tika` node. Check it by hand.

**Fix:** convert property indexes to Lucene, add the Tika configuration, set `async`, and keep `compatVersion` at 2.

## AEMCS-008: Customised DAM Update Asset workflow
- **Impact:** High
- **Adobe rule:** `CloudServiceIncompatibleWorkflowProcess` (Bug, Major)
- **Evidence:** Documented. The list of unsupported step classes is in `workflowSteps.properties` in Adobe's `aem-cloud-migration` repository, not in the docs.
- **Adobe skill:** `assetApi` (asset API calls only)
- **Scanner:** `dam/update_asset` workflow models and launchers in package content.

**Fix:** move renditions to processing profiles. Supported custom steps can run in a post-processing workflow, configured through `CustomDamWorkflowRunnerImpl` or a folder's auto-start workflow setting. The model must end with the "DAM Update Asset Workflow Completed Process" step. Launchers aren't needed. See [Configure asset microservices][assets].

## AEMCS-009: Classic UI dialogs
- **Impact:** High
- **Adobe rule:** `ComponentWithOnlyClassicUIDialog`, `ClassicUIAuthoringMode` (Code Smell, Minor)
- **Evidence:** Documented. Classic UI is no longer available.
- **Adobe skill:** `lui` (dialogs), `cdw` (custom ExtJS widgets)
- **Scanner:** `dialog.xml`, `design_dialog.xml` and `cq:Dialog` nodes.

**What to check:** whether each component also has a Touch UI `cq:dialog`. If it doesn't, authors can't edit it, and the quality step still passes.

## AEMCS-021: Static templates and foundation components
- **Impact:** Medium
- **Adobe rule:** `StaticTemplateUsage`, `LegacyFoundationComponentUsage` (Code Smell, Minor)
- **Evidence:** Documented as discouraged, not removed. Design data under `/apps` can't be edited at runtime.
- **Adobe skill:** Template Modernization
- **Scanner:** `cq:Template` nodes under `/apps`, and `sling:resourceSuperType` values starting with `foundation/components/`.

**Fix:** move to editable templates and Core Components. Adobe's AEM Modernization Tools help with templates. See [Notable Changes][changes].

---

# Dispatcher

## AEMCS-010: Dispatcher configuration not in Cloud Service format
- **Impact:** Blocker
- **Adobe rule:** None on the quality-rules page. The Dispatcher validator enforces it.
- **Evidence:** Documented
- **Adobe skill:** `dispatcherConversion`
- **Scanner:** a dispatcher module without `src/conf.d` and `src/conf.dispatcher.d`, or a `dispatcher.any` outside `conf.dispatcher.d/`.

**Why:** AEMaaCS doesn't accept a customer-written monolithic `dispatcher.any` or `httpd.conf`. Configuration must follow the Cloud layout, in which 11 files (including `conf.dispatcher.d/dispatcher.any`) are Adobe-owned and must not be changed.

**Validation** has three phases: the validator (directive allow-list and filter checks), `httpd -t` in Docker, and an immutability check. Cloud Manager runs `httpd -t` in its Build Images step.

**Also note:** `mod_security` **is** supported on AEMaaCS, while `mod_expires` isn't on the module list.

**Fix:** convert with Adobe's Dispatcher Converter (in `adobe/aem-cloud-service-source-migration`). AMS configs convert almost automatically. On-premise configs need more review. See [Validating and Debugging Dispatcher Tools][dispval].

## AEMCS-024: Dispatcher in legacy mode
- **Impact:** Medium
- **Adobe rule:** None
- **Evidence:** Documented. Legacy mode is still accepted, and Adobe strongly recommends flexible mode.
- **Adobe skill:** `dispatcherConversion`
- **Scanner:** a Cloud-layout dispatcher module with no `opt-in/USE_SOURCES_DIRECTLY` file.

**Why:** legacy mode limits customisable files to under 1 MB in total and one rewrite file. Newer features, such as pipeline-free redirects, need flexible mode.

**Fix:** add `opt-in/USE_SOURCES_DIRECTLY` and re-run the validator. See [Dispatcher in the Cloud][disp].

---

# Not covered by the scanner

Check these by hand, or with Adobe's Best Practices Analyzer on a running instance:

- Repository-level findings: content size, node counts, users and groups, production indexes.
- Service users and ACLs that should move to repoinit.
- The full Dispatcher directive allow-list (run `validator allowlist` from the Dispatcher SDK).
- Overlapping packages and duplicate OSGi configs (`PackageOverlaps`, `DuplicateOsgiConfigurations`).
- Mail service, advanced networking and integrations that use JWT service accounts.
- Forms, Screens, Commerce and Dynamic Media specifics.

[cqr]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/using-cloud-manager/test-results/custom-code-quality-rules
[skill]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/migration-journey/cloud-migration-skill/using-cloud-migration-skill
[dep]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/release-notes/deprecated-removed-features
[structure]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/developing/aem-project-content-package-structure
[osgi]: https://experienceleague.adobe.com/docs/experience-manager-cloud-service/implementing/deploying/configuring-osgi.html
[deploy]: https://experienceleague.adobe.com/docs/experience-manager-cloud-service/implementing/deploying/overview.html
[sdk]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/developing/aem-as-a-cloud-service-sdk
[build]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/using-cloud-manager/create-application-project/build-environment-details
[kblog]: https://experienceleague.adobe.com/en/docs/experience-cloud-kcs/kbarticles/ka-35915
[logfwd]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/developing/log-forwarding
[repl]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/operations/replication
[dev]: https://experienceleague.adobe.com/docs/experience-manager-cloud-service/implementing/developing/development-guidelines.html
[index]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/operations/indexing
[assets]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/assets/manage/asset-microservices-configure-and-use
[changes]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/release-notes/aem-cloud-changes
[dispval]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/content-delivery/validation-debug
[disp]: https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/implementing/content-delivery/disp-overview
