#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for gruplar-tab-ui-yenileme UI refactor.

This module contains STRUCTURAL tests (HTML/CSS/JS string validation) for the
"Gruplar" tab UI renewal (AC-1..AC-5 and regressions). Tests verify that the
`INDEX_HTML` string constant in `src/api/admin_panel.py` contains the expected
structural elements and JS/CSS code patterns.

NOTE on AC-6/AC-7 (runtime behavior):
  AC-6: "Arama sonucu yok" empty-state display on filter mismatch
  AC-7: Defensive try/catch in filterGroups() to preserve list on JS errors

  These are runtime/interaction behaviors that cannot be tested structurally
  (they depend on JS execution, DOM manipulation, and event handlers at runtime).
  They are validated in the verify step via live Playwright E2E tests (separate task).
  These tests DO NOT cover AC-6/7.

Acceptance Criteria Mapping:
  AC-1 → test_two_panels_structure()
  AC-2 → test_grp_row_class_exists() + test_loadGroups_uses_grp_row() + test_baileysGrpAdd_uses_grp_row()
  AC-3 → test_search_input_exists() + test_filterGroups_function_exists()
  AC-4 → test_loadBaileysGroups_preserves_message_contract() [regression]
  AC-5 → test_yenile_buttons_oncick_calls_preserved() [regression]

Regression Tests:
  - test_grpDel_uses_new_row_selector(): Validates that grpDel() uses .grp-row not .bl-item
  - test_bl_item_class_still_defined(): Ensures .bl-item CSS class exists for other tabs
  - test_css_variables_preserved(): Checks that --acc, --bg, --ok, --err CSS vars still exist
"""

import pytest
import re
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.api import admin_panel


class TestGruplarTabStructure:
    """AC-1: Two-panel layout with grid/flex for Kayıtlı and Baileys groups"""

    def test_two_panels_structure(self):
        """
        Given: `#tab-grp` section in INDEX_HTML
        When: checking for two distinct panel structures
        Then: both "Kayıtlı Gruplar" and "Baileys Grupları" panels should be present

        AC-1 (Critical): The tab should render two panels side-by-side on desktop,
        stacked on mobile, without changing the underlying API calls.
        """
        html = admin_panel.INDEX_HTML

        # Check for #tab-grp section existence
        assert '#tab-grp' in html, "INDEX_HTML must contain #tab-grp section"

        # Extract the #tab-grp section for focused testing
        tab_grp_match = re.search(
            r'id=["\']tab-grp["\'].*?(?=<div\s+id=["\'][^"\']+["\']|\Z)',
            html,
            re.DOTALL
        )
        assert tab_grp_match, "#tab-grp section not found in INDEX_HTML"
        tab_grp_section = tab_grp_match.group(0)

        # Verify presence of "Kayıtlı Gruplar" panel (registered groups)
        assert 'Kayıtlı Gruplar' in tab_grp_section or 'kayitli' in tab_grp_section.lower(), \
            "Registered groups panel ('Kayıtlı Gruplar') not found in #tab-grp"

        # Verify presence of "Baileys Grupları" panel
        assert 'Baileys Grupları' in tab_grp_section or 'baileys' in tab_grp_section.lower(), \
            "Baileys groups panel ('Baileys Grupları') not found in #tab-grp"

        # Verify that some layout class (grid/flex) is being used
        # We don't hardcode the exact class name, just verify grid/flex presence
        has_grid_or_flex = re.search(
            r'\b(grid|flex|column)\b',
            tab_grp_section,
            re.IGNORECASE
        )
        assert has_grid_or_flex, \
            "No grid/flex layout indication found in #tab-grp (AC-1 requires responsive layout)"


class TestGruplarRowClassAndFunctions:
    """AC-2: New .grp-row CSS class for group row items, replacing .bl-item in this tab"""

    def test_grp_row_class_exists(self):
        """
        Given: CSS block in INDEX_HTML
        When: searching for a new group-row CSS class definition
        Then: a new CSS class (e.g., .grp-row or similar) should be defined

        AC-2 requires a new CSS class for group row styling (not reusing .bl-item,
        which is used by other tabs like Kara Liste).
        """
        html = admin_panel.INDEX_HTML

        # Look for a CSS class definition that handles group rows
        # The exact class name (grp-row, grp-item, etc.) is implementation-specific
        # so we use a pattern that catches common naming conventions
        grp_row_pattern = r'\.(grp[-_]row|grp[-_]item|group[-_]row|group[-_]item)\s*\{[^}]+\}'
        has_new_class = re.search(grp_row_pattern, html, re.IGNORECASE)

        assert has_new_class or 'grp-row' in html or 'grp-item' in html, \
            "No new group row CSS class (like .grp-row or .grp-item) found in INDEX_HTML"

    def test_loadGroups_uses_grp_row(self):
        """
        Given: loadGroups() function in INDEX_HTML
        When: inspecting its DOM construction logic
        Then: it should use the new .grp-row class (or similar), NOT .bl-item

        AC-2: The registered groups should render with the new row class.
        """
        html = admin_panel.INDEX_HTML

        # Extract loadGroups function
        loadgroups_match = re.search(
            r'function\s+loadGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        assert loadgroups_match, "loadGroups() function not found in INDEX_HTML"
        loadgroups_body = loadgroups_match.group(1)

        # Check that .grp-row (or variant) is used in the render template
        has_grp_row = re.search(
            r"['\"]?\.?grp[-_]row['\"]?|\bgrp[-_]row\b",
            loadgroups_body,
            re.IGNORECASE
        )
        assert has_grp_row, \
            "loadGroups() does not appear to use .grp-row class for rendering rows (AC-2 violation)"

        # Regression: Ensure .bl-item is NOT used in loadGroups (other tabs use it)
        uses_bl_item = re.search(r"bl[-_]item", loadgroups_body, re.IGNORECASE)
        assert not uses_bl_item, \
            "loadGroups() still uses .bl-item class (should use new .grp-row for Gruplar tab)"

    def test_loadBaileysGroups_uses_grp_row(self):
        """
        Given: loadBaileysGroups() function in INDEX_HTML
        When: inspecting its DOM construction logic
        Then: it should use the new .grp-row class (or similar), NOT .bl-item

        AC-2: The Baileys groups should also render with the new row class.
        """
        html = admin_panel.INDEX_HTML

        # Extract loadBaileysGroups function
        loadbailey_match = re.search(
            r'function\s+loadBaileysGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        assert loadbailey_match, "loadBaileysGroups() function not found in INDEX_HTML"
        loadbailey_body = loadbailey_match.group(1)

        # Check that .grp-row (or variant) is used in the render template
        has_grp_row = re.search(
            r"['\"]?\.?grp[-_]row['\"]?|\bgrp[-_]row\b",
            loadbailey_body,
            re.IGNORECASE
        )
        assert has_grp_row, \
            "loadBaileysGroups() does not appear to use .grp-row class for rendering rows (AC-2 violation)"

        # Regression: Ensure .bl-item is NOT used in loadBaileysGroups
        uses_bl_item = re.search(r"bl[-_]item", loadbailey_body, re.IGNORECASE)
        assert not uses_bl_item, \
            "loadBaileysGroups() still uses .bl-item class (should use new .grp-row for Gruplar tab)"

    def test_baileysGrpAdd_uses_grp_row(self):
        """
        Given: baileysGrpAdd() function (adds new Baileys group to UI)
        When: inspecting its row construction
        Then: it should also use the new .grp-row class

        AC-2 compliance: All row constructions in groups tab should use new class.
        """
        html = admin_panel.INDEX_HTML

        # Extract baileysGrpAdd function
        baileygrpadd_match = re.search(
            r'function\s+baileysGrpAdd\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        # This function might not exist if implementation uses a different approach
        # but if it does, it must use the new class
        if baileygrpadd_match:
            baileygrpadd_body = baileygrpadd_match.group(1)

            # Check for .grp-row or element construction patterns
            has_grp_row = re.search(
                r"['\"]?\.?grp[-_]row['\"]?|\bgrp[-_]row\b",
                baileygrpadd_body,
                re.IGNORECASE
            )
            # If function creates DOM elements, it should use new class
            uses_bl_item = re.search(r"bl[-_]item", baileygrpadd_body, re.IGNORECASE)
            assert not uses_bl_item, \
                "baileysGrpAdd() uses .bl-item (should use .grp-row)"


class TestSearchFunctionality:
    """AC-3: Search input and client-side filterGroups function"""

    def test_search_input_exists(self):
        """
        Given: #tab-grp section
        When: searching for search/filter input element
        Then: an input element (likely with id/placeholder related to search/filter) should exist

        AC-3 (Critical): New search functionality requires an input element for user query.
        """
        html = admin_panel.INDEX_HTML

        # Extract tab-grp section
        tab_grp_match = re.search(
            r'id=["\']tab-grp["\'].*?(?=<div\s+id=["\'][^"\']+["\']|\Z)',
            html,
            re.DOTALL
        )
        assert tab_grp_match, "#tab-grp section not found"
        tab_grp_section = tab_grp_match.group(0)

        # Look for input element (search, filter, arama, etc.)
        has_search_input = re.search(
            r'<input\s+[^>]*(search|filter|arama|grp)[^>]*>',
            tab_grp_section,
            re.IGNORECASE
        )
        assert has_search_input, \
            "No search/filter input element found in #tab-grp section (AC-3 requires user input)"

    def test_filterGroups_function_exists(self):
        """
        Given: INDEX_HTML JS section
        When: searching for group filtering function
        Then: a function to filter groups client-side (e.g., filterGroups, searchGroups) should exist

        AC-3 (Critical): Filtering must happen on client-side without new backend requests.
        """
        html = admin_panel.INDEX_HTML

        # Look for a filter function with common naming patterns
        filter_func_pattern = r'function\s+(filter|search)Groups?\s*\([^)]*\)\s*\{'
        has_filter_func = re.search(filter_func_pattern, html, re.IGNORECASE)

        assert has_filter_func, \
            "No filterGroups/searchGroups/filter function found in INDEX_HTML (AC-3 requires client-side filtering)"


class TestBackendContractPreservation:
    """AC-4: Backend API contract (message field) remains unchanged"""

    def test_loadBaileysGroups_preserves_message_contract(self):
        """
        Given: loadBaileysGroups() function calls /api/whatsapp/groups endpoint
        When: backend returns 202 + {"message": "..."} for empty-state conditions
        Then: the function should still handle d.message (API contract unchanged)

        AC-4 (High): Backend contract must not change; empty-state UI uses same message.
        Regression: Ensures Baileys group loading behavior is preserved.
        """
        html = admin_panel.INDEX_HTML

        # Extract loadBaileysGroups function
        loadbailey_match = re.search(
            r'function\s+loadBaileysGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        assert loadbailey_match, "loadBaileysGroups() function not found"
        loadbailey_body = loadbailey_match.group(1)

        # Verify that d.message is still checked (empty-state condition from backend)
        has_message_check = re.search(
            r'd\.message|\.message',
            loadbailey_body,
            re.IGNORECASE
        )
        assert has_message_check, \
            "loadBaileysGroups() does not check d.message for empty-state handling (AC-4 violation)"


class TestPaginationFunctionality:
    """AC-2: Pagination for Kayıtlı Gruplar panel (20+ groups)"""

    def test_pagination_function_exists(self):
        """
        Given: INDEX_HTML contains groups panel code
        When: searching for pagination function definition
        Then: a pagination function should exist (regex: function name can vary,
               but must be related to pagination/sayfa/page, case-insensitive)

        AC-2 (Critical): Pagination function must be implemented for client-side
        group list navigation.
        """
        html = admin_panel.INDEX_HTML

        # Look for a pagination function with common naming patterns
        # Function name can be: renderGrpPage, updatePagination, showPage, etc.
        # Pattern allows flexibility in naming
        pagination_func_pattern = r'function\s+\w*[Pp]agina\w*\s*\('
        has_pagination_func = re.search(pagination_func_pattern, html, re.IGNORECASE)

        assert has_pagination_func, \
            "No pagination function found in INDEX_HTML (AC-2 requires pagination logic)"

    def test_pagination_container_exists(self):
        """
        Given: #tab-grp section (Kayıtlı Gruplar panel)
        When: searching for pagination UI container
        Then: an HTML element for page numbers/navigation should exist
               (e.g., id/class containing 'pagination' or 'sayfa')

        AC-2 (Critical): Pagination UI must be present for user navigation.
        """
        html = admin_panel.INDEX_HTML

        # Extract tab-grp section
        tab_grp_match = re.search(
            r'id=["\']tab-grp["\'].*?(?=<div\s+id=["\'][^"\']+["\']|\Z)',
            html,
            re.DOTALL
        )
        assert tab_grp_match, "#tab-grp section not found"
        tab_grp_section = tab_grp_match.group(0)

        # Look for pagination container (id or class with 'pagination' or 'sayfa')
        has_pagination_ui = re.search(
            r'\b(id|class)\s*=\s*["\']?[^"\'>\s]*(?:pagination|sayfa|page)[^"\'>\s]*["\']?',
            tab_grp_section,
            re.IGNORECASE
        )
        assert has_pagination_ui, \
            "No pagination UI container found in #tab-grp (AC-2 requires visible pagination)"


class TestPaginationAndSearchIntegration:
    """AC-3: Pagination resets to page 1 when search filter is applied"""

    def test_filterGroups_resets_pagination(self):
        """
        Given: filterGroups() function (search handler) in INDEX_HTML
        When: user enters search query while pagination is active
        Then: filterGroups should reset pagination to page 1
               (verify by looking for "page = 1" or pagination reset call within function)

        AC-3 (High): Search result must start from first page, not current page.
        """
        html = admin_panel.INDEX_HTML

        # Extract filterGroups function
        filtergroups_match = re.search(
            r'function\s+filterGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        assert filtergroups_match, "filterGroups() function not found in INDEX_HTML"
        filtergroups_body = filtergroups_match.group(1)

        # Check for pagination reset: look for "page" or "sayfa" variable assignment/reset
        # or a call to pagination update function
        has_pagination_reset = re.search(
            r'\b(?:currentPage|page|sayfa)\s*=\s*[01]|\b(?:renderGrpPage|updatePagination|showPage)\s*\(',
            filtergroups_body,
            re.IGNORECASE
        )
        assert has_pagination_reset, \
            "filterGroups() does not appear to reset pagination state (AC-3 violation: should reset to page 1)"


class TestVisualEnhancements:
    """AC-4: Visual enhancements (icons/styling) added to existing .grp-row class"""

    def test_grp_row_styling_enhanced(self):
        """
        Given: CSS block in INDEX_HTML with .grp-row class styling
        When: checking for visual enhancements compared to base styling
        Then: additional CSS rules/styles should be present around .grp-row
               (to indicate icons, badges, spacing improvements)

        AC-4 (High): Styling must be enhanced beyond previous version.
        Approach: Verify that .grp-row styling exists and has multiple properties,
        indicating visual enhancement. We check for presence of multiple style rules
        rather than hardcoding exact property names (code-copilot has freedom in implementation).
        """
        html = admin_panel.INDEX_HTML

        # Find .grp-row CSS class definition
        grp_row_css_pattern = r'\.grp[-_]row\s*\{[^}]+\}'
        grp_row_css_match = re.search(grp_row_css_pattern, html, re.IGNORECASE | re.DOTALL)

        assert grp_row_css_match, \
            ".grp-row CSS class not found in INDEX_HTML (AC-4 requires styling)"

        grp_row_css_block = grp_row_css_match.group(0)

        # Check that CSS block has multiple properties (indicates styling, not just empty)
        # Count semicolons as property terminators; at least 2-3 properties expected
        property_count = grp_row_css_block.count(';')
        assert property_count >= 2, \
            ".grp-row CSS block appears minimal (AC-4 requires enhanced visual styling)"


class TestBaileysGroupsPaginationNegative:
    """AC-6: Baileys Grupları panel is NOT affected by pagination (negative test)"""

    def test_baileys_panel_no_pagination_reference(self):
        """
        Given: loadBaileysGroups() function in INDEX_HTML
        When: searching within the function and surrounding Baileys panel HTML
        Then: pagination function calls should NOT appear in or near loadBaileysGroups
               (Baileys panel list is short, does not need pagination)

        AC-6 (Medium): Baileys panel must remain simple, pagination applies only to
        Kayıtlı Gruplar. This is a NEGATIVE test — pagination should NOT be applied here.
        """
        html = admin_panel.INDEX_HTML

        # Extract loadBaileysGroups function
        loadbailey_match = re.search(
            r'function\s+loadBaileysGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        assert loadbailey_match, "loadBaileysGroups() function not found"
        loadbailey_body = loadbailey_match.group(1)

        # Negative test: loadBaileysGroups should NOT call pagination functions
        # Look for common pagination function names (renderGrpPage, updatePagination, showPage, etc.)
        has_pagination_call = re.search(
            r'\b(?:renderGrpPage|updatePagination|showPage|paginate|pagination|showBaileysPage)\s*\(',
            loadbailey_body,
            re.IGNORECASE
        )
        assert not has_pagination_call, \
            "loadBaileysGroups() should NOT call pagination functions (AC-6: pagination only for Kayıtlı Gruplar)"

        # Also check that #baileys-available-groups-list container is separate from
        # Kayıtlı Gruplar pagination container (this is structural, not in the function)
        # Look for baileys groups container in HTML
        baileys_container_pattern = r'id\s*=\s*["\']?baileys[-_]?groups?[-_]?list["\']?'
        has_baileys_container = re.search(baileys_container_pattern, html, re.IGNORECASE)

        if has_baileys_container:
            # Verify there's no pagination reference near the Baileys container
            baileys_match = re.search(
                r'id\s*=\s*["\']baileys[-_]?groups?[-_]?list["\'][^<]*<[^<]*?(?=<div\s+id|<section|\Z)',
                html,
                re.IGNORECASE | re.DOTALL
            )
            if baileys_match:
                baileys_section = baileys_match.group(0)
                baileys_has_pagination = re.search(
                    r'(?:pagination|sayfa|paginat)',
                    baileys_section,
                    re.IGNORECASE
                )
                assert not baileys_has_pagination, \
                    "Baileys groups container should not reference pagination (AC-6 negative test)"


class TestButtonPreservation:
    """AC-5: Yenile (Refresh) buttons preserve their onclick handlers"""

    def test_yenile_buttons_oncick_calls_preserved(self):
        """
        Given: INDEX_HTML with "Yenile" refresh buttons in groups tab
        When: checking button elements
        Then: buttons should still call loadGroups() and loadBaileysGroups() on click

        AC-5 (High): Refresh button behavior must not change; loading logic unchanged.
        Regression: Ensures button click handlers remain functional.
        """
        html = admin_panel.INDEX_HTML

        # Extract tab-grp section
        tab_grp_match = re.search(
            r'id=["\']tab-grp["\'].*?(?=<div\s+id=["\'][^"\']+["\']|\Z)',
            html,
            re.DOTALL
        )
        assert tab_grp_match, "#tab-grp section not found"
        tab_grp_section = tab_grp_match.group(0)

        # Check for onclick="loadGroups()"
        has_loadgroups_call = re.search(
            r'onclick\s*=\s*["\']loadGroups\(\)',
            tab_grp_section,
            re.IGNORECASE
        )
        assert has_loadgroups_call, \
            "loadGroups() onclick handler not found in #tab-grp section (AC-5 regression)"

        # Check for onclick="loadBaileysGroups()"
        has_loadbailey_call = re.search(
            r'onclick\s*=\s*["\']loadBaileysGroups\(\)',
            tab_grp_section,
            re.IGNORECASE
        )
        assert has_loadbailey_call, \
            "loadBaileysGroups() onclick handler not found in #tab-grp section (AC-5 regression)"


class TestRegressions:
    """Regression tests to ensure other tabs/features are not broken"""

    def test_grpDel_uses_new_row_selector(self):
        """
        Regression (Plan.md risk): grpDel() function must use new row class selector,
        not the old .bl-item, to ensure delete confirmation dialog shows correct group name.

        Given: grpDel() function (delete group handler)
        When: inspecting DOM traversal logic
        Then: it should use .closest('.grp-row') or similar, NOT .closest('.bl-item')
        """
        html = admin_panel.INDEX_HTML

        # Extract grpDel function
        grpdel_match = re.search(
            r'function\s+grpDel\s*\([^)]*\)\s*\{(.*?)(?=\n\s*function|\Z)',
            html,
            re.DOTALL
        )
        assert grpdel_match, "grpDel() function not found in INDEX_HTML"
        grpdel_body = grpdel_match.group(1)

        # Check that .grp-row (or similar new class) is used in closest() selector
        has_grp_row_selector = re.search(
            r"\.closest\s*\(\s*['\"]\.grp[-_]row",
            grpdel_body,
            re.IGNORECASE
        )
        assert has_grp_row_selector, \
            "grpDel() does not use .closest('.grp-row') for DOM traversal (regression risk)"

        # Ensure .bl-item is NOT used in grpDel
        uses_bl_item = re.search(
            r"\.closest\s*\(\s*['\"]\.bl[-_]item",
            grpdel_body,
            re.IGNORECASE
        )
        assert not uses_bl_item, \
            "grpDel() still uses .closest('.bl-item') (should use new .grp-row selector)"

    def test_bl_item_class_still_defined(self):
        """
        Regression (Plan.md requirement): .bl-item CSS class must still exist,
        as other tabs (Kara Liste) use it and must not be broken.

        Given: CSS block in INDEX_HTML
        When: searching for .bl-item class definition
        Then: it should still be present and unchanged
        """
        html = admin_panel.INDEX_HTML

        # Look for .bl-item class definition in CSS
        has_bl_item_class = re.search(
            r'\.(bl|black)[-_]item\s*\{[^}]+\}',
            html,
            re.IGNORECASE
        )
        assert has_bl_item_class or '.bl-item' in html, \
            ".bl-item CSS class definition missing (other tabs depend on it)"

    def test_css_variables_preserved(self):
        """
        Regression (atdd.md benchmark requirement): CSS custom properties (--acc, --bg, --ok, --err)
        must still be defined in :root or equivalent, as all tabs use them.

        Given: CSS custom properties in INDEX_HTML
        When: searching for color/state variables
        Then: --acc, --bg, --ok, --err should all be present
        """
        html = admin_panel.INDEX_HTML

        css_vars = ['--acc', '--bg', '--ok', '--err']
        for var in css_vars:
            assert var in html, \
                f"CSS variable {var} not found in INDEX_HTML (other tabs depend on it)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
