# Cloud Service blocker catalogue

Each rule says what the scanner looks for, why it matters on AEM as a Cloud Service (AEMaaCS), how to confirm it, and the usual fix. Severities are defaults. Adjust them after looking at the code.

> Status: v0.1. Rules are written from hands-on migration experience. Before you rely on a rule, check it against Adobe's current AEM as a Cloud Service documentation, because the platform changes often.

---

## AEMCS-001: Mutable content deployed with immutable code
**Default severity:** Blocker

**Scanner looks for:** a `META-INF/vault/filter.xml` in one content package that has roots under both `/apps` (or `/libs`) **and** mutable paths such as `/content`, `/conf`, `/etc`, `/var`, `/home` or `/oak:index`.

**Why:** on AEMaaCS, `/apps` and `/libs` are immutable at runtime and are deployed as part of the container image. Mutable content is installed separately. A package that mixes both is rejected by the Cloud Manager build.

**Confirm:** open each flagged `filter.xml` and list its roots.

**Fix:** split into `ui.apps` (immutable `/apps` only), `ui.content` (mutable content) and `ui.config` (OSGi configs), all embedded in an `all` container package. The current AEM Project Archetype is the reference layout.

---

## AEMCS-002: OSGi configuration in a legacy format
**Default severity:** Major

**Scanner looks for:** OSGi configs as `sling:OsgiConfig` nodes in `.content.xml`/`.xml` files, or as `.config` / `.cfg` files, inside `config*` folders.

**Why:** AEMaaCS expects OSGi configuration as `.cfg.json` files. Legacy formats are unsupported or flagged by the build's code-quality checks.

**Confirm:** check the folder names (`config`, `config.author`, `config.publish.prod` …) and the file format.

**Fix:** convert each config to `<PID>.cfg.json` (or `<factoryPID>~<name>.cfg.json`). Move secrets and environment-specific values to Cloud Manager environment variables, using `$[env:VAR]` / `$[secret:VAR]` placeholders.

---

## AEMCS-003: Custom run modes
**Default severity:** Blocker

**Scanner looks for:** `config.<x>` folders where `<x>` is anything other than `author`, `publish`, `dev`, `stage`, `prod` or a supported combination such as `author.dev` or `publish.prod`.

**Why:** AEMaaCS only supports the `author`/`publish` service run modes and the `dev`/`stage`/`prod` environment run modes. Configs in other folders, such as `config.uat` or `config.local`, are silently ignored, so behaviour quietly changes.

**Confirm:** list all `config.*` folders and check what each one configures.

**Fix:** fold custom environments into `dev`/`stage`/`prod`. Use Cloud Manager environment variables for values that differ per environment.

---

## AEMCS-004: Administrative sessions and resource resolvers
**Default severity:** Blocker

**Scanner looks for:** `loginAdministrative(`, `getAdministrativeResourceResolver(` and `getAdministrativeSession(` in Java code.

**Why:** administrative logins have long been deprecated, and AEMaaCS doesn't allow them. Code that relies on them fails at runtime.

**Confirm:** open each call site. Check what the code reads or writes.

**Fix:** create a service user with least-privilege ACLs (repoinit in `ui.config`), map it with a `ServiceUserMapperImpl.amended` config, and use `ResourceResolverFactory.getServiceResourceResolver()` with the subservice name.

---

## AEMCS-005: Replication agents and the Replicator API
**Default severity:** Major

**Scanner looks for:** replication agent definitions under `/etc/replication` in content packages, and custom code using `com.day.cq.replication` (`Replicator`, `ReplicationAction`, `AgentManager`).

**Why:** AEMaaCS publishes content through Sling Content Distribution, not classic replication agents. Custom agent configurations don't carry over. Code that inspects agents or queues breaks, though basic `Replicator.replicate()` calls may still work.

**Confirm:** separate *agent configuration* (always a problem) from *simple publish calls* (often fine) and *agent/queue introspection* (a problem).

**Fix:** remove agent configs. Review custom publishing logic against the Cloud Service content distribution model, and use the Sling Distribution APIs where queue control is needed.

---

## AEMCS-006: Custom Oak index definitions
**Default severity:** Major

**Scanner looks for:** `oak:QueryIndexDefinition` nodes in content packages.

**Why:** on AEMaaCS, custom indexes must be deployed through the code pipeline and follow the Cloud Service naming convention, `<indexName>-custom-<n>` for new indexes or customised product indexes. Indexes installed the old way, or named differently, are not applied.

**Confirm:** list each index, its name and what queries depend on it.

**Fix:** rename and version the indexes to the Cloud Service convention and deploy them in the `ui.apps`/index package. Re-test the queries that use them.

---

## AEMCS-007: Writing to the local filesystem
**Default severity:** Major

**Scanner looks for:** `new FileOutputStream(`, `new FileWriter(`, `Files.write(`, `Files.newOutputStream(` and `File.createTempFile(` in Java code.

**Why:** AEMaaCS runs as containers that scale and restart. Local disk is temporary and not shared between instances. Anything written there for later use (exports, caches, generated files) can disappear.

**Confirm:** check whether the file is short-lived scratch space (usually fine) or expected to persist or be shared (a problem).

**Fix:** keep persistent data in the repository or in external storage (for example cloud blob storage). Keep temp files strictly short-lived.

---

## AEMCS-008: Customised DAM Update Asset workflow
**Default severity:** Major

**Scanner looks for:** overlays or copies of the `dam/update_asset` workflow model, and workflow launchers configured for asset creation or modification under `/conf` or `/etc/workflow`.

**Why:** AEMaaCS processes assets with asset microservices, not the DAM Update Asset workflow. Custom steps added to that workflow don't run the same way.

**Confirm:** list the custom steps and what each one does: renditions, metadata or integrations.

**Fix:** move renditions to processing profiles. Move the remaining custom logic to a post-processing workflow, which is configured in the folder's processing profile or workflow settings.

---

## AEMCS-009: Classic UI dialogs and components
**Default severity:** Minor (Major if authors still depend on them)

**Scanner looks for:** `dialog.xml` / `design_dialog.xml` files, and nodes with `jcr:primaryType="cq:Dialog"` (ExtJS Classic UI).

**Why:** Classic UI isn't available on AEMaaCS. Components with only Classic UI dialogs can't be edited in the Touch UI.

**Confirm:** check whether each component also has a `cq:dialog` (Granite/Touch UI) node.

**Fix:** convert dialogs to Granite UI (`_cq_dialog/.content.xml`). Adobe's AEM Modernization Tools can automate much of this.

---

## AEMCS-010: Dispatcher configuration not in Cloud Service format
**Default severity:** Major

**Scanner looks for:** a dispatcher module without the Cloud Service layout, which needs `src/conf.d` and `src/conf.dispatcher.d` with `available_*`/`enabled_*` folders. It also looks for the legacy single `dispatcher.any` file.

**Why:** the AEMaaCS dispatcher only accepts configuration in the immutable/flexible-mode file structure, and the Cloud Manager pipeline validates it.

**Confirm:** compare the module layout with the dispatcher folder of the current AEM Project Archetype. Run the Dispatcher SDK validator locally.

**Fix:** restructure the config to the Cloud Service layout. Adobe's Dispatcher Converter handles most of the mechanical work. Review rewrites and filters by hand afterwards.
