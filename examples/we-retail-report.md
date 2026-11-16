# AEM as a Cloud Service readiness assessment: We.Retail

**Assessed:** 16 November 2026 · **AEM baseline:** `uber-jar` 6.3.1.2, Java 1.8 · **Modules:** `parent`, `config`, `core`, `ui.apps`, `ui.content`, `it.tests.ui-js`, `all`
**Source:** [Adobe-Marketing-Cloud/aem-sample-we-retail](https://github.com/Adobe-Marketing-Cloud/aem-sample-we-retail) at commit `fb38f38` (11 September 2019), Apache-2.0
**Basis:** code repository only. No running instance or BPA report was used.

> This is a sample report. We.Retail is Adobe's former reference site for AEM 6.x. Adobe archived it in 2019 and replaced it with WKND, and it was never meant to run on Cloud Service. That makes it a fair public stand-in for a real legacy codebase. Nothing here is criticism of the project. For the control case, see the [WKND report](wknd-report.md).

## Summary

We.Retail can't be deployed to AEM as a Cloud Service as it is. The scanner raised 38 candidates across 9 rules. After checking each in context, 10 findings remain: 3 blockers, 4 high, 2 medium and 1 low. Two candidates were dismissed.

The mechanical work is small, because the codebase is small (35 Java classes, 45 components): new project structure, new build, OSGi annotations and a handful of API swaps. A rough estimate is 1 to 2 weeks for one developer who knows AEM. This estimate is a judgment from the code, not a measurement.

The real question is not in that list. More than half the Java classes are built on AEM's classic commerce framework, which the scanner doesn't cover. Whether to port that code or replace it with Adobe's current commerce integration decides the true size of the migration. See "Not assessed".

| Impact | Count |
| --- | --- |
| Blocker | 3 |
| High | 4 |
| Medium | 2 |
| Low | 1 |

## Deadlines

Rule AEMCS-013 applies. Five classes import libraries on Adobe's second removal batch, dated 31 December 2027 and mostly marked tentative. Rule AEMCS-011 covers packages that are already removed, so those have no grace period. Check the dates on Adobe's [Deprecated and Removed Features](https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/release-notes/deprecated-removed-features) page before planning around them.

## Findings

### [Blocker] AEMCS-011: Felix SCR annotations
- **Where:** `core/src/main/java/we/retail/core/WeRetailCommerceServiceFactory.java:18` and 3 similar files (17 imports in total): `CartEntryServlet.java`, `SimilarToCartRelationshipsProvider.java`, `SimilarToCurrentRelationshipsProvider.java`
- **What we found:** services are declared with `org.apache.felix.scr.annotations` (`@Component`, `@Service`, `@Property`), processed by `maven-scr-plugin` in `parent/pom.xml`.
- **Why it matters on Cloud Service:** this annotation library and its Maven plugin are retired in favour of the standard OSGi Declarative Services annotations. The build has to move to a current JDK, and the old plugin doesn't come along.
- **Adobe rule:** Build Analyzer import check (`api-regions-exportsimports`)
- **Evidence:** Documented that the package is removed. That the build fails is inferred: these are build-time annotations, so the failure is expected in the Maven plugin on a newer JDK, not in the analyser. Confirm with a build on JDK 17 or 21.
- **Fix:** replace with `org.osgi.service.component.annotations`, move properties into `@Component(property = …)` or an `@ObjectClassDefinition`, and replace `maven-scr-plugin` and `maven-bundle-plugin` with `bnd-maven-plugin`.
- **Fix with:** manual. The change is mechanical and the same in all four files.
- **Effort:** S

### [Blocker] AEMCS-011: Guava import
- **Where:** `core/src/main/java/we/retail/core/model/CountriesFormOptionsDataSource.java:44`
- **What we found:** `import com.google.common.collect.ImmutableMap;`
- **Why it matters on Cloud Service:** Guava is no longer exported by the AEM runtime, so the bundle can't resolve the package.
- **Adobe rule:** Build Analyzer import check (`api-regions-exportsimports`)
- **Evidence:** Documented that the package is removed. That the build fails on it is inferred from how the analyser works.
- **Fix:** use `java.util.Map.of(…)` or `Collections.unmodifiableMap(…)`.
- **Fix with:** manual. Adobe's skill has a `guavaCache` pattern, but it covers Guava caches only.
- **Effort:** S

### [Blocker] No Dispatcher module
- **Where:** the project root. There is no `dispatcher` module.
- **What we found:** the repository has no Dispatcher configuration at all, so the scanner had nothing to flag under AEMCS-010.
- **Why it matters on Cloud Service:** a Cloud Manager project needs a Dispatcher module in the Cloud Service layout. The configuration this site ran with lives somewhere else and has to be found and converted.
- **Adobe rule:** none on the quality-rules page. The Dispatcher validator enforces the layout.
- **Evidence:** Documented
- **Fix:** generate a module from the current AEM Project Archetype, then port the site's rules into it and opt in to flexible mode.
- **Fix with:** Adobe skill pattern `dispatcherConversion`, once the existing configuration is located.
- **Effort:** M

### [High] AEMCS-001: Mutable and immutable content in one package
- **Where:** `ui.apps/src/main/content/META-INF/vault/filter.xml`
- **What we found:** the package installs `/apps/weretail/…` together with `/var/commerce/payment-methods/we-retail` and `/var/commerce/shipping-methods/we-retail`.
- **Why it matters on Cloud Service:** `/apps` is immutable and ships in the image. `/var` is mutable and is installed separately. One package can't do both.
- **Adobe rule:** `ImmutableMutableMixedPackage` (Code Smell, Minor)
- **Evidence:** Documented. That the build fails is inferred.
- **Fix:** move the two `/var/commerce` roots to `ui.content`. Split the project into `ui.apps`, `ui.config` and `ui.content`, embedded in an `all` package with typed package types.
- **Fix with:** manual
- **Effort:** S

### [High] AEMCS-014 and AEMCS-015: Build targets AEM 6.3 and Java 8
- **Where:** `parent/pom.xml:573` (`uber-jar` 6.3.1.2), also `core/pom.xml` and `ui.apps/pom.xml`; `parent/pom.xml:126` (source and target 1.8); no `.cloudmanager/java-version`
- **What we found:** the build compiles against the 6.3 API jar with Java 8, using `content-package-maven-plugin`.
- **Why it matters on Cloud Service:** the API jar is now `aem-sdk-api`, the runtime is Java 21, and the build must run on JDK 17 or 21.
- **Adobe rule:** none
- **Evidence:** Documented, except that Adobe doesn't call uber-jar "unsupported" in so many words.
- **Fix:** depend on `com.adobe.aem:aem-sdk-api`, add `.cloudmanager/java-version`, move to `filevault-package-maven-plugin` and add `aemanalyser-maven-plugin`. The simplest route is a fresh project from the current archetype, with the code moved in.
- **Fix with:** manual
- **Effort:** M

### [High] AEMCS-020: Custom log file
- **Where:** `config/src/content/jcr_root/apps/weretail/config/org.apache.sling.commons.log.LogManager.factory.config-we-retail.xml`
- **What we found:** `org.apache.sling.commons.log.file="logs/project-we-retail.log"`
- **Why it matters on Cloud Service:** Java logs go to `logs/error.log` only. The `file` and `pattern` properties are ignored, so anyone looking for `project-we-retail.log` finds nothing.
- **Adobe rule:** Build Analyzer `configuration-api`
- **Evidence:** Documented
- **Fix:** keep the logger for `we.retail` at the right level and drop the `file` and `pattern` properties.
- **Fix with:** manual, together with the OSGi format change below.
- **Effort:** S

### [High] AEMCS-013: APIs removed on 31 December 2027 (tentative)
- **Where:** `core/src/main/java/we/retail/core/WeRetailCommerceServiceImpl.java:26` and 4 similar: `WeRetailCommerceSessionImpl.java`, `OrderHistoryModel.java`, `ShoppingCartModel.java` (commons-collections 3), `ProductItem.java` (`org.apache.sling.commons.json`)
- **What we found:** imports of `org.apache.commons.collections.Predicate`, `CollectionUtils` and `org.apache.sling.commons.json.JSONObject`.
- **Why it matters on Cloud Service:** both libraries are on Adobe's removal list. Cloud Manager reports them today as deprecated-API issues, and the severity rises as the date gets closer.
- **Adobe rule:** `java:S1874`; `CQRules:AMSCORE-553` (Code Smell, Minor)
- **Evidence:** Documented, with the date mostly marked tentative
- **Fix:** move to commons-collections4 or plain Java streams, and to a supported JSON library.
- **Fix with:** manual
- **Effort:** S

### [Medium] AEMCS-021: Components extend a foundation component
- **Where:** `ui.apps/src/main/content/jcr_root/apps/weretail/components/structure/productfilter/.content.xml` and `…/productreviews/.content.xml`
- **What we found:** `sling:resourceSuperType="foundation/components/parbase"`
- **Why it matters on Cloud Service:** foundation components are discouraged, not removed. The page templates are already editable templates under `/conf`, so this is limited to two components.
- **Adobe rule:** `LegacyFoundationComponentUsage` (Code Smell, Minor)
- **Evidence:** Documented as discouraged
- **Fix:** remove the supertype where nothing is inherited, or move to a Core Component.
- **Fix with:** manual
- **Effort:** S

### [Medium] AEMCS-009: Leftover Classic UI dialog
- **Where:** `ui.apps/src/main/content/jcr_root/apps/weretail/components/structure/productreviews/dialog.xml`
- **What we found:** a Classic UI `dialog.xml` next to a Touch UI `_cq_dialog`.
- **Why it matters on Cloud Service:** authors are not blocked, because the Touch UI dialog exists. The Classic one is dead code, and Classic UI is gone. The default impact for this rule is High; it is lowered here for that reason.
- **Adobe rule:** `ClassicUIAuthoringMode` (Code Smell, Minor)
- **Evidence:** Documented
- **Fix:** delete `dialog.xml`.
- **Fix with:** manual
- **Effort:** S

### [Low] AEMCS-002: OSGi configuration in a superseded format
- **Where:** `config/src/content/jcr_root/apps/weretail/config/` (3 files) and `config.publish/` (1 file): three `sling:OsgiConfig` XML nodes and one `.config` file
- **What we found:** configurations for the logger, the service user mapping, the form mail servlet and the root mapping servlet in the older formats.
- **Why it matters on Cloud Service:** Adobe calls these formats superseded by `.cfg.json`. They are not called unsupported.
- **Adobe rule:** none
- **Evidence:** Documented
- **Fix:** convert to `<PID>.cfg.json` and move them to a `ui.config` module.
- **Fix with:** Adobe skill pattern `osgi-cloud-manager`
- **Effort:** S

## Candidates checked and dismissed

- **AEMCS-001** in `it.tests.ui-js/src/main/content/META-INF/vault/filter.xml`: the filter mixes `/apps/weretail/tests` with `/content` and `/etc`. This is a test package that the README says is not for production. It would not be deployed to Cloud Service, so it is not counted. If the tests are kept, they need a new home.
- **AEMCS-009** in `ui.apps/src/main/content/jcr_root/apps/msm/we-retail/blueprintconfigs/weretail/_jcr_content/dialog.xml`: this is a Multi Site Manager blueprint configuration, with the structure the product itself writes. It is not a component dialog. Marked as inferred, since Adobe's docs don't describe the node.

## Fix plan

In order, quick wins first. Work on a branch.

1. **Manual:** create a new project from the current AEM Project Archetype and move `core`, `ui.apps` and `ui.content` into it. This settles AEMCS-014, AEMCS-015 and the missing Dispatcher module in one step.
2. **Manual:** move the two `/var/commerce` filter roots from `ui.apps` to `ui.content` (AEMCS-001).
3. **Adobe skill**, one session:
   ```
   Use the migration skill, manual flow, no BPA report: convert the OSGi configurations in config/src/content/jcr_root/apps/weretail/config and config/src/content/jcr_root/apps/weretail/config.publish
   ```
   Then remove the `file` and `pattern` properties from the logger config by hand (AEMCS-020).
4. **Manual:** convert the four Felix SCR classes to OSGi annotations, and replace the Guava, commons-collections and Sling JSON imports (AEMCS-011, AEMCS-013).
5. **Manual:** delete the leftover `dialog.xml` and review the two `foundation/components/parbase` supertypes (AEMCS-009, AEMCS-021).
6. **Adobe skill**, once the old Dispatcher configuration is found: the `dispatcherConversion` pattern.

**Custom code that may not be needed on Cloud Service:** the whole commerce layer. See below.

## Not assessed

- **Classic commerce.** 19 of the 35 Java classes import `com.adobe.cq.commerce` (97 imports), and the site's catalogue, cart and order pages depend on it. The scanner has no rule for this; the rule catalogue lists classic commerce under "check by hand". Adobe's commerce integration on Cloud Service is a different design, with an external commerce backend. Whether to port this code or replace it is a product decision, and it outweighs every finding above. A first technical check is to compile `core` against `aem-sdk-api` and read the errors.
- **Service users.** The service user mapping names `commerce-orders-service` and `content-reader-service`. The repository doesn't create them. On Cloud Service they and their permissions belong in repoinit.
- **Groups in a content package.** `ui.content` installs `/home/groups/projects/admin/we_retail`. Users and groups need their own plan on Cloud Service.
- **Form mail.** The site configures the foundation form mail servlet. Outbound mail on Cloud Service needs advanced networking. No mail service configuration is in the repository.
- Things that need a running instance or Adobe tooling: content size, production indexes, integrations, and BPA or Cloud Acceleration Manager results.

## Recommended next steps

1. Decide what happens to the commerce layer. Don't estimate the rest until this is settled.
2. Run steps 1 to 5 of the fix plan. They are independent of the commerce decision.
3. Build on JDK 21 with `aemanalyser-maven-plugin` and deploy to the local Cloud SDK.
4. Run Best Practices Analyzer on a 6.5 instance that has the site installed, and compare its findings with this report.
