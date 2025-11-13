# Issues and Improvements Tracker

**Generated:** 2025-11-13
**Context:** Educational repository for teaching Elastic, OpenSearch, and Elastic OSS

This document tracks identified issues and improvements for the flavours-of-elastic repository, prioritized from P0 (critical) to P3 (nice to have).

---

## P0 - Critical Issues (Breaks Functionality)

### 1. Bug: Wrong variable in elk-oss Dockerfile
- **Location:** `docker/elk-oss/Dockerfile:8`
- **Issue:** Uses `$ELK_VERSION` instead of `$ELK_OSS_VERSION` for plugin installation
- **Impact:** Plugin installation will fail when students build the image
- **Fix:** Change to `$ELK_OSS_VERSION`

### 2. Bug: Syntax error in elk-oss docker-compose
- **Location:** `docker/elk-oss/docker-compose.yml:39`
- **Issue:** `cluster.initial_master_nodes:elk-oss-node1` uses `:` instead of `=`
- **Impact:** elk-oss-node2 will fail to start, students will get errors
- **Fix:** Change to `cluster.initial_master_nodes=elk-oss-node1,elk-oss-node2`

### 3. Documentation: Outdated version information
- **Location:** `README.md:8-11`
- **Issue:** README shows OpenSearch 2.9.0 and Elastic 8.9.1, but `.env` has 2.17.1 and 8.15.2
- **Impact:** Students see inconsistent information and get confused about what they're running
- **Fix:** Update README to match actual versions or reference `.env` file

---

## P1 - High Priority (Poor Student Experience)

### 4. Documentation: Missing .env setup instructions
- **Location:** `README.md:21-22`
- **Issue:** Says "fill in .env file" but .env already exists with values
- **Impact:** Students might think they need to create the file or change values
- **Fix:** Clarify that .env is pre-configured for local development, or document how to customize

### 5. Documentation: Incorrect credentials in README
- **Location:** `README.md:29`
- **Issue:** Says to use `-u admin:admin` for OpenSearch but actual password is in `.env` (strong password)
- **Impact:** Students can't connect to OpenSearch, curl commands fail
- **Fix:** Update README to reference the `.env` password or note default credentials

### 6. Configuration: Missing ELASTIC_PASSWORD in es02
- **Location:** `docker/elk/docker-compose.yml:102-140`
- **Issue:** `es02` service doesn't set `ELASTIC_PASSWORD` environment variable (es01 has it at line 74)
- **Impact:** Inconsistent node configuration, potential authentication issues
- **Fix:** Add `ELASTIC_PASSWORD=${ELASTIC_PASSWORD}` to es02 environment variables

### 7. Documentation: No quickstart guide
- **Issue:** Students need to read entire README to understand which section to use
- **Impact:** Confusion about which docker-compose file to run first
- **Fix:** Add "Quick Start" section at the top with 3 clear paths (ELK/OpenSearch/ELK-OSS)

### 8. Documentation: No prerequisites section
- **Issue:** Doesn't mention minimum Docker/RAM requirements
- **Impact:** Students with limited resources will have silent failures
- **Fix:** Add system requirements (RAM, Docker version, disk space)

---

## P2 - Medium Priority (Usability Improvements)

### 9. Configuration: No .env.example for reference
- **Issue:** If students want to customize, no clean template exists
- **Impact:** Students might break configuration
- **Fix:** Create `.env.example` with documentation comments explaining each variable

### 10. Documentation: No troubleshooting section
- **Issue:** Common student problems (port conflicts, memory limits) aren't documented
- **Impact:** Students get stuck on common issues
- **Fix:** Add troubleshooting section with common errors and solutions:
  - Port 9200 already in use
  - Out of memory errors
  - Docker not running
  - max_map_count issues on Linux

### 11. Documentation: Benchmarking instructions unclear
- **Location:** `README.md:46-77`
- **Issue:** Benchmark instructions jump between tools without clear separation
- **Impact:** Students confused about which tool for which stack
- **Fix:** Restructure with clear subsections: "For Elastic Stack" and "For OpenSearch"

### 12. Code Quality: Commented-out code in elk-oss
- **Location:** `docker/elk-oss/docker-compose.yml:18-24, 50-56, 74-75`
- **Issue:** Large blocks of commented security configuration
- **Impact:** Confusing for students - is this needed or not?
- **Fix:** Remove or move to separate example file with explanation

### 13. Documentation: No "What's the difference?" section
- **Issue:** Students don't understand when to use Elastic vs OpenSearch vs Elastic OSS
- **Impact:** Students pick wrong version for their needs
- **Fix:** Add comparison table explaining:
  - Elastic Stack (latest, commercial features)
  - OpenSearch (open source alternative, AWS-backed)
  - Elastic OSS (legacy 7.x support)

### 14. Configuration: Deprecated Docker Compose version
- **Location:** `docker/elk/docker-compose.yml:1`
- **Issue:** Uses `version: "2.2"` while others use `3.7`
- **Impact:** Inconsistent, students learn outdated syntax
- **Fix:** Upgrade to version 3.x

### 15. Configuration: Inconsistent Java heap sizes
- **Locations:**
  - ELK: 1G (`docker/elk/docker-compose.yml:87`)
  - OpenSearch: 2G (`docker/opensearch/docker-compose.yml:12`)
  - ELK-OSS: 512M (`docker/elk-oss/docker-compose.yml:11`)
- **Issue:** No explanation why different
- **Impact:** Students on low-RAM machines might struggle with OpenSearch
- **Fix:** Document rationale or provide notes on adjusting for available RAM

### 16. Code Quality: Personal path in OpenSearch Dockerfile
- **Location:** `docker/opensearch/Dockerfile:9`
- **Issue:** Comment has `/Users/konstantinp/projects/`
- **Impact:** Looks unprofessional, students might think it's required
- **Fix:** Use generic path or remove personal reference

### 17. Configuration: No healthcheck for es02 dependencies
- **Location:** `docker/elk/docker-compose.yml:104`
- **Issue:** `es02` depends on `es01` but doesn't use `condition: service_healthy`
- **Impact:** Occasional race conditions during startup
- **Fix:** Add `condition: service_healthy` like kibana does

### 18. Documentation: Pre-commit hooks not mentioned
- **Location:** `.pre-commit-config.yaml` exists
- **Issue:** Students contributing don't know to set up pre-commit
- **Impact:** Inconsistent contributions
- **Fix:** Add development section mentioning pre-commit setup

---

## P3 - Low Priority (Nice to Have)

### 19. Documentation: No learning path suggestions
- **Issue:** No guidance on "start with X, then try Y"
- **Impact:** Students don't know recommended learning sequence
- **Fix:** Add suggested learning path (e.g., "Start with ELK-OSS, then OpenSearch, then modern Elastic")

### 20. Documentation: No sample queries/commands
- **Issue:** After starting, students don't know what to do next
- **Impact:** Minimal hands-on learning
- **Fix:** Add "Next Steps" section with:
  - Basic index creation
  - Sample document insertion
  - Simple queries
  - Dashboard access

### 21. Documentation: No architecture diagrams
- **Issue:** Students don't visualize the multi-node setup
- **Impact:** Less understanding of cluster concepts
- **Fix:** Add simple ASCII or Mermaid diagrams showing node relationships

### 22. Testing: No validation script
- **Issue:** Students don't know if setup worked correctly
- **Impact:** Silent failures or partial setups
- **Fix:** Add `verify.sh` or `verify.py` script that checks:
  - All containers running
  - Health endpoints responding
  - Can create test index
  - Dashboards accessible

### 23. Documentation: No cleanup instructions
- **Issue:** No guidance on stopping and cleaning up volumes
- **Impact:** Students accumulate docker volumes, waste disk space
- **Fix:** Add cleanup section with:
  - `docker-compose down` (stop)
  - `docker-compose down -v` (stop and remove volumes)
  - Clean restart instructions

### 24. Documentation: Missing links to official docs
- **Issue:** No links to Elastic/OpenSearch official documentation
- **Impact:** Students don't know where to learn more
- **Fix:** Add "Learn More" section with curated links to:
  - Elastic official docs
  - OpenSearch documentation
  - Community forums

### 25. Dependencies: No version constraint on PyYAML
- **Location:** `requirements.txt:1`
- **Issue:** `PyYAML` has no version
- **Impact:** Different students get different versions
- **Fix:** Pin to specific version (e.g., `PyYAML==6.0.1`)

### 26. Configuration: No example with single node
- **Issue:** All setups use 2-node clusters
- **Impact:** Students with limited RAM (< 8GB) can't run any examples
- **Fix:** Add single-node variants for resource-constrained machines or document how to comment out second node

### 27. Documentation: No video tutorials or screenshots
- **Issue:** Text-only README
- **Impact:** Visual learners struggle
- **Fix:** Add screenshots of:
  - Kibana dashboard
  - OpenSearch Dashboards
  - Sample queries in Dev Tools

### 28. Documentation: No common use cases examples
- **Issue:** No examples of "why would I use this?"
- **Impact:** Students don't see practical applications
- **Fix:** Add use case section:
  - Log aggregation and analysis
  - Full-text search
  - Metrics and analytics
  - Application monitoring

---

## Summary Statistics

- **P0 (Critical):** 3 issues
- **P1 (High):** 5 issues
- **P2 (Medium):** 10 issues
- **P3 (Low):** 10 issues
- **Total:** 28 issues

## Recommended Implementation Order

1. **First iteration:** Fix P0 issues (bugs preventing functionality)
2. **Second iteration:** Address P1 issues (student experience)
3. **Third iteration:** Tackle high-impact P2 issues (documentation, troubleshooting)
4. **Ongoing:** Add P3 enhancements as time permits

---

## Contributing

When working on these issues:
- Reference the issue number in commit messages (e.g., "fix: correct elk-oss variable #1")
- Update this document when issues are resolved
- Add checkboxes: `- [x]` for completed items
