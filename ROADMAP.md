# First MCP Server - Project Roadmap

## Project Vision

Transform this MCP server from a monolithic tool collection into a modular, distributable Python package ecosystem. The goal is to create specialized MCP servers that can be easily installed, configured, and maintained.

## Version History

### v1.0.0 ✅ Released
- Complete FastMCP server with memory, weather, workspace, calculator, and calendar tools
- Memory system with TinyDB backend
- Universal server timestamp integration across all tool responses
- Auto-initialization for fresh installs

### v1.1.0 ✅ Released
- Tool pruning: 52 → 32 tools (38% reduction for better UX)
- Architecture delegation pattern: MCP ↔ Server ↔ Data layers
- 3-tier test structure: server/data/intelligence separation
- Smart tag mapping integrated into `tinydb_memorize`
- Removed experimental tools: governance, aliases, maintenance

### v1.1.1 ⚠️ Not Released (stashed as WIP)
The following features were designed and partially implemented but never completed or tested:
- **Configurable tag limits** via environment variables (e.g. `FIRST_MCP_MAX_TAGS`)
- **`MemoryConfig` class** for runtime configuration management
- **`configure_memory_settings()` MCP tool** for adjusting memory behaviour at runtime
- **`get_system_info()` enhancement** to display memory config state

These ideas remain valid — tag proliferation is a known problem — but the implementation was abandoned before testing. The stash is preserved as `stash@{0}` on branch `feature/v1.1.1-tag-limit`.

### v1.2.0 ✅ Released
New `embeddings.py` data layer and two MCP tools for semantic similarity scoring:
- **`compute_text_similarity(query, text, context?, text_weight?, context_weight?)`** — cosine similarity with optional context blending via weighted embedding average
- **`rank_texts_by_similarity(query, candidates)`** — rank a list of texts by relevance to a query
- **`weighted_combine_embeddings()`** — normalized weighted sum of two embedding vectors (data layer)
- `tag_tools.py` and `semantic_search.py` refactored to import from `embeddings.py` (no duplication)
- `--version` / `-V` CLI flag — prints version and exits cleanly
- Data processing tests (20) and MCP layer tests (5) — all passing

### v1.2.1 ✅ Released
Embedding model migration and batch API efficiency:
- Switched from `text-embedding-004` (unavailable) to `gemini-embedding-001` (3072-dim)
- Added `generate_embeddings_batch()` — embeds a list of texts per API call instead of one call per text
- `regenerate_all_tag_embeddings()` rewritten to use batched calls
- Added `google-genai` and `numpy` as `[embeddings]` optional dependency in `pyproject.toml`

### v1.2.2 ✅ Released (current `main`)
Auto-migration of tag embeddings at startup:
- Added `check_and_migrate_tag_embeddings()` service function — compares stored `embedding_model` field on tag records against `EMBEDDING_MODEL` constant; triggers batch regeneration automatically if mismatched
- Wired into `main()` startup sequence — future embedding model changes are self-healing
- Removed roadmap duplication: `__init__.py` now contains only a brief package description; `ROADMAP.md` is the single source of truth

### v1.3.0 ✅ Released
New tools extending workspace and adding biblical text lookup:
- **`workspace_edit_textfile(filename, mode, content, anchor?)`** — anchor-based in-place text editing with six modes: `append`, `prepend`, `insert_after`, `insert_before`, `replace`, `replace_all`. Designed for long-running MCP tasks that build composite outputs incrementally. No line numbers needed — the client reads the file first and uses a nearby text string as the anchor.
- **`bible_lookup(reference, bible_version?)`** — looks up ESV biblical text by reference string. Supports single verses (`"John 3:16"`), verse ranges (`"Matt 5:3-12"`), full chapters (`"Ps 23"`), chapter ranges (`"Gen 1-4"`), and semicolon-separated multi-references. Bible data (ESV) is downloaded automatically from `github.com/lguenth/mdbible` on first use and cached locally under `$FIRST_MCP_DATA_PATH/bible_data/ESV/`. The version parameter is designed for future translation support.
- **`src/first_mcp/bible/`** — new subpackage: `canonical.py`, `sources.py` (ESVBibleDownloader), `books.py` (VerseAccessor, spaCy-free markdown parser), `lookup.py` (BibleLookup with per-version accessor cache). Wesley sermon support deliberately excluded to avoid web-scraping dependencies.
- Bug fix: `normalize_book_name()` now correctly round-trips canonical names containing Roman numerals (e.g. `"II_Samuel"` was incorrectly returning `"Ii_Samuel"` via `.title()`)
- Tests: 18 data-processing tests for workspace edit, 29 data-processing tests for bible module, MCP-layer tests for both tools

### v1.3.0 ✅ Released
New tools extending workspace and adding biblical text lookup:
- **`workspace_edit_textfile(filename, mode, content, anchor?)`** — anchor-based in-place text editing with six modes: `append`, `prepend`, `insert_after`, `insert_before`, `replace`, `replace_all`. Designed for long-running MCP tasks that build composite outputs incrementally. No line numbers needed — the client reads the file first and uses a nearby text string as the anchor.
- **`bible_lookup(reference, bible_version?)`** — looks up ESV biblical text by reference string. Supports single verses, verse ranges, full chapters, chapter ranges, and semicolon-separated multi-references. Bible data (ESV) is downloaded automatically from `github.com/lguenth/mdbible` on first use and cached under `$FIRST_MCP_DATA_PATH/bible_data/ESV/`. The version parameter is designed for future translation support.
- **`src/first_mcp/bible/`** — new subpackage: `canonical.py`, `sources.py` (ESVBibleDownloader), `books.py` (VerseAccessor, spaCy-free markdown parser), `lookup.py` (BibleLookup with per-version accessor cache). Wesley sermon support deliberately excluded to avoid web-scraping dependencies.
- Bug fix: `normalize_book_name()` now correctly round-trips canonical names containing Roman numerals (e.g. `"II_Samuel"` was incorrectly returning `"Ii_Samuel"` via `.title()`)
- Tests: 18 data-processing tests for workspace edit, 29 for bible module, MCP-layer tests for both tools

## Version 2.0 - Modular Architecture 🚧

**Target**: Q1 2025

**Foundation**: Building on v1.0's universal timestamp system and optimized tool set

### Core Goals
- **Modular Design**: Split functionality into specialized servers
- **PyPI Distribution**: Prepare for package distribution  
- **Clean Separation**: Distinct servers with clear responsibilities
- **Backward Compatibility**: Maintain existing tool interfaces including universal timestamp support
- **Enhanced Timestamps**: Leverage timestamp system for advanced time-based features

### Tag Management (deferred from v1.1.1)
- Tag proliferation prevention (configurable limits, env-var config) — see v1.1.1 stash
- Tag governance, consolidation workflows — planned for v2.0

### 2.0 Deliverables - Safe Operations Architecture 🛡️

**Priority Enhancement**: Universal Safe Operations Pattern

#### Safe Operations Framework
- **Client Transparency**: Claude Desktop client knows nothing about dry runs
- **Server Intelligence**: Tools use management classes in execution mode by default
- **Test Safety**: `test_client.py` automatically operates all tools in dry-run mode
- **Explicit Override Pattern**: Applied to all memory and workspace management modules
  - Memory operations (create, update, delete memories)
  - Tag management (consolidate, prune, standardize) 
  - Workspace operations (file creation, modification)
  - Database operations (create, update, delete records)

#### Implementation Pattern
```python
# Server tools (execution mode by default)
@mcp.tool()
def consolidate_tags(rules: List[Dict]):
    manager = TagManager(dry_run=False)  # Real execution
    return manager.consolidate_tags(rules)

# Test environment detection
def is_test_environment() -> bool:
    return 'test_client.py' in sys.argv[0] or 'pytest' in sys.modules

# Automatic test safety
if is_test_environment():
    manager = TagManager(dry_run=True)  # Safe for tests
```

#### 2.1 - Repository Structure & CI/CD
- [ ] GitHub repository with proper branching strategy
- [ ] Python package structure (`src/first_mcp/`)
- [ ] Setup.py and pyproject.toml for PyPI
- [ ] GitHub Actions for testing and release automation
- [ ] Semantic versioning implementation

#### 2.2 - Memory-First Modular Architecture  
- [ ] **Core Package** (`first-mcp`) - Memory system + basic utilities as foundation
- [ ] **Workspace Extension** (`first-mcp[workspace]`) - Optional file management features
- [ ] **Weather Extension** (`first-mcp[weather]`) - Optional weather and geocoding services
- [ ] **Complete Package** (`first-mcp[all]`) - All extensions bundled

#### 2.3 - Enhanced Memory System
- [ ] Evaluate memory system spec v0.2 recommendations
- [ ] Implement practical improvements (2-3 primary tools vs 15)
- [ ] Maintain backward compatibility for existing memories
- [ ] Add semantic intelligence where feasible without heavy ML deps
- [ ] **Timestamp-aware Memory**: Leverage universal timestamps for temporal memory features
- [ ] **Time-based Queries**: Enable memory search by time ranges using server timestamps

##### 2.3.1 - Semantic Search & Tag Quality (CRITICAL)
- [ ] **High-Performance Semantic Search**: Dramatically improve semantic search efficiency and accuracy
- [ ] **Tag Proliferation Prevention**: Implement robust mechanisms to prevent duplicate and similar tag creation
- [ ] **Intelligent Tag Consolidation**: Automatic detection and merging of semantically equivalent tags
- [ ] **Tag Quality Metrics**: Implement tag usage analytics and quality scoring
- [ ] **Advanced Tag Similarity**: Enhanced similarity algorithms beyond basic string matching
- [ ] **Tag Governance System**: Automated tag cleanup and standardization processes

**Quality Requirements for v2.0:**
- **Zero Tag Proliferation**: New memories must reuse existing similar tags with >95% accuracy
- **Sub-100ms Semantic Search**: Tag similarity and memory search must complete in <100ms
- **High-Quality Tag Set**: Maintain clean, consistent tag taxonomy with automatic deduplication
- **Intelligent Suggestions**: Tag suggestions must find existing similar tags with >90% precision

#### 2.4 - Package Distribution Preparation
- [ ] Memory-first installation (`pip install first-mcp` = core memory system)
- [ ] Optional extensions (`pip install first-mcp[workspace,weather,all]`)
- [ ] Configuration management system
- [ ] Docker support for easy deployment
- [ ] Documentation overhaul for memory-first architecture

## Memory-First Architecture Philosophy

### Core Vision: Memory as Foundation
The first-mcp package is built around **intelligent memory management** as its core value proposition:

```bash
# Default installation - Memory system with basic utilities
pip install first-mcp

# Optional extensions for specialized use cases  
pip install first-mcp[workspace]    # + File management
pip install first-mcp[weather]      # + Weather services
pip install first-mcp[all]         # + All extensions
```

### Package Structure
- **Core Memory System**: Always included - intelligent storage, retrieval, categorization
- **Basic Utilities**: Calculator, calendar, system info (lightweight foundation)
- **Optional Extensions**: Workspace and weather as separate modules
- **Unified Configuration**: Single configuration approach across all modules

### User Experience
- **Immediate Value**: `pip install first-mcp` gives users powerful memory management
- **Progressive Enhancement**: Add features as needed without bloat
- **Consistent Interface**: All extensions integrate seamlessly with memory system
- **Cloud-Ready**: Designed for both local and cloud deployment scenarios

## Version 3.0 - Advanced Features 🔮

**Target**: Q2 2025

### Planned Enhancements
- **Plugin Architecture**: Third-party server extensions
- **Advanced Memory AI**: Optional ML-based semantic search with vector embeddings
- **Multi-backend Support**: Beyond TinyDB (SQLite, PostgreSQL) with optimized indexing
- **Claude Desktop Integration**: Streamlined setup and configuration
- **Performance Optimizations**: Caching, indexing, bulk operations
- **Advanced Temporal Features**: Time-series analysis, timestamp-based analytics using universal timestamp foundation
- **Production-Grade Semantic Search**: Vector databases (Chroma, Qdrant) for large-scale deployments
- **Enterprise Tag Management**: Advanced tag taxonomy management for large organizations

## Development Principles

### Versioning Strategy
- **Major versions** (1.0, 2.0, 3.0): Breaking changes, architectural shifts
- **Minor versions** (2.1, 2.2): New features, non-breaking changes  
- **Patch versions** (2.1.1): Bug fixes, security updates

### Compatibility Commitment
- **Data compatibility**: Existing TinyDB files must work across versions
- **API compatibility**: Tool interfaces maintained where reasonable
- **Configuration compatibility**: Smooth upgrade paths

### Quality Standards
- **Testing**: Comprehensive test coverage for all servers
- **Documentation**: Clear setup guides and API documentation  
- **Performance**: Response time benchmarks and optimization
- **Security**: Input validation and safe file operations
- **Temporal Consistency**: Universal timestamp implementation across all tool responses
- **Time-aware Testing**: Validation of timestamp accuracy, format compliance, and timezone handling

## Migration Strategy

### Phase 1: Safe Modularization (v2.1)
1. Extract servers while maintaining identical tool interfaces
2. Add integration tests to verify functionality parity
3. Create migration documentation and scripts
4. Maintain server.py as legacy fallback

### Phase 2: Optimization (v2.2-2.3)  
1. Optimize individual servers for their specific use cases
2. Implement memory system improvements based on practical evaluation
3. Add package distribution infrastructure
4. Begin deprecation notices for legacy patterns

### Phase 3: Advanced Features (v2.4+)
1. Add optional advanced features (ML, cloud backends)
2. Plugin system for community extensions
3. Performance and scalability improvements
4. Full PyPI ecosystem integration

## Risk Management

### Technical Risks
- **Data Migration**: TinyDB file compatibility across versions
- **Breaking Changes**: Tool interface modifications affecting Claude Desktop
- **Performance**: Ensuring modular servers don't introduce latency
- **Tag Quality Crisis**: Current v1.0 system allows unlimited tag proliferation
- **Semantic Search Bottlenecks**: String-based similarity matching doesn't scale efficiently
- **Memory System Complexity**: 15 memory tools create user confusion and maintenance overhead

### Current v1.0 Limitations (Must Address in v2.0)
- **Tag Proliferation Problem**: Users can create infinite similar tags (e.g., "python", "Python", "python-dev", "python_development")
- **Inefficient Semantic Search**: Simple string matching in `tinydb_find_similar_tags()` has poor accuracy
- **No Tag Governance**: No automated cleanup or consolidation of duplicate/similar tags
- **Performance Degradation**: Tag similarity searches become slower as tag database grows
- **User Experience Issues**: Complex memory workflow requires multiple tool calls for optimal results

### Mitigation Strategies
- **Comprehensive Testing**: All scenarios covered before release
- **Rollback Plans**: Git tags for stable fallback versions
- **Gradual Migration**: Optional adoption of new features
- **User Communication**: Clear upgrade guides and change logs

#### v2.0 Specific Mitigations
- **Tag Migration Strategy**: Automated analysis and consolidation of existing tag databases
- **Performance Benchmarking**: Continuous performance monitoring during semantic search redesign
- **Backward Compatibility**: Maintain existing tag structures while implementing quality improvements
- **User Experience Testing**: Validate simplified memory workflows don't break existing usage patterns

## Success Metrics

### v2.0 Success Criteria
- [ ] All existing functionality available across modular servers
- [ ] Universal timestamp system preserved across all modular components
- [ ] PyPI package installable and functional
- [ ] <10% performance regression from v1.0 baseline (including timestamp overhead)
- [ ] 100% data migration success rate
- [ ] Comprehensive documentation for all servers
- [ ] Temporal consistency maintained across distributed server architecture

#### Memory System Performance Benchmarks (CRITICAL)
- [ ] **Semantic Search Performance**: <100ms response time for tag similarity queries
- [ ] **Tag Quality Metrics**: >95% accuracy in preventing duplicate tag creation
- [ ] **Memory Search Efficiency**: <200ms for complex memory queries with semantic expansion
- [ ] **Tag Consolidation Success**: Automated detection of 90%+ of duplicate/similar tags
- [ ] **Zero Tag Proliferation**: New tag creation rate <5% when similar tags exist

### Community Goals
- [ ] GitHub repository with clear contribution guidelines
- [ ] Active issue tracking and community engagement
- [ ] Third-party server examples and documentation
- [ ] Claude Desktop integration guides

## Repository Information

**GitHub**: https://github.com/TobiSan5/first-mcp  
**Author**: Torbjørn Wikestad (@TobiSan5)

## Long-term Vision

Create a thriving ecosystem of MCP servers that can be:
- **Easily installed** via pip/conda
- **Simply configured** for Claude Desktop  
- **Extended by community** through plugin architecture
- **Scaled for production** use cases
- **Maintained sustainably** with clear ownership

---

**Maintained by**: Torbjørn Wikestad
**Last Updated**: 2026-02-16
**Next Review**: On v2.0 planning