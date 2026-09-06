#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for blacklist-pagination feature.

This module contains STRUCTURAL tests (HTML/CSS/JS string validation) for the
blacklist pagination UI refactor (AC-1..AC-5 and regressions). Tests verify that the
`INDEX_HTML` string constant in `src/api/admin_panel.py` contains the expected
structural elements and JS/CSS code patterns.

NOTE on runtime behavior (AC-5/AC-6):
  AC-5: "Son sayfadaki kayıt silinince bir önceki sayfaya dönme" (automatic via loadBl() reset)
  AC-6: "Pagination hatasının ana liste render'ını etkilememesi" (isolation test)

  These are runtime/interaction behaviors that cannot be tested structurally
  (they depend on JS execution, DOM manipulation, and event handlers at runtime).
  They are validated in the verify step via live e2e tests (separate task).
  These tests DO NOT cover AC-5/AC-6 runtime verification.

Acceptance Criteria Mapping:
  AC-1 → test_bl_pagination_html_section_exists()
  AC-2 (func) → test_bl_pagination_function_exists()
  AC-2 (state) → test_bl_pagination_function_uses_bl_current_page()
  AC-2 (style) → test_bl_pagination_uses_acc_button_class() + test_bl_pagination_uses_arrow_characters()
  AC-3 → test_bl_pagination_visibility_logic()
  AC-4 → test_loadBl_calls_renderBlPagination()

Regression Tests:
  - test_items_per_page_not_redefined(): Validates that ITEMS_PER_PAGE is not re-declared
  - test_bl_item_class_preserved(): Ensures .bl-item CSS class exists (used by loadBl)
  - test_grp_pagination_functions_preserved(): Validates that Gruplar pagination is untouched
  - test_grpSearchMatches_variable_preserved(): Ensures Gruplar' state variable is unchanged
"""

import pytest
import re
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.api import admin_panel


class TestBlacklistPaginationHtmlStructure:
    """AC-1: Pagination HTML section in blacklist tab"""

    def test_bl_pagination_html_section_exists(self):
        """
        Given: `#tab-bl` section in INDEX_HTML
        When: checking for pagination container
        Then: `#bl-pagination` section should be present in HTML

        AC-1 (Critical): Pagination UI container must exist in the DOM.
        """
        html = admin_panel.INDEX_HTML

        # Check for #tab-bl section existence
        assert re.search(r'id=["\']tab-bl["\']', html), "INDEX_HTML must contain the tab-bl div"

        # Extract the #tab-bl section for focused testing
        tab_bl_match = re.search(
            r'id=["\']tab-bl["\'].*?(?=<div\s+id=["\'][^"\']+["\']|\Z)',
            html,
            re.DOTALL
        )
        assert tab_bl_match, "#tab-bl section not found in INDEX_HTML"
        tab_bl_section = tab_bl_match.group(0)

        # Verify presence of #bl-pagination section
        has_bl_pagination = re.search(
            r'id\s*=\s*["\']bl-pagination["\']',
            tab_bl_section,
            re.IGNORECASE
        )
        assert has_bl_pagination, \
            "#bl-pagination section not found in #tab-bl (AC-1 requires pagination container)"


class TestBlacklistPaginationFunction:
    """AC-2: renderBlPagination function implementation"""

    def test_bl_pagination_function_exists(self):
        """
        Given: INDEX_HTML JS section
        When: searching for pagination function definition
        Then: a `renderBlPagination(page)` function should be defined

        AC-2 (Critical): Pagination function must exist for client-side navigation.
        """
        html = admin_panel.INDEX_HTML

        # Look for renderBlPagination function definition
        pagination_func_pattern = r'function\s+renderBlPagination\s*\('
        has_pagination_func = re.search(pagination_func_pattern, html, re.IGNORECASE)

        assert has_pagination_func, \
            "renderBlPagination() function not found in INDEX_HTML (AC-2 requires pagination logic)"

    def test_bl_pagination_function_uses_bl_current_page(self):
        """
        Given: renderBlPagination(page) function in INDEX_HTML
        When: inspecting variable usage for pagination state
        Then: it should use `blCurrentPage` variable (isolated from Gruplar' currentPage)

        AC-2 (Critical): Isolated pagination state for blacklist (not shared with groups).
        Regression: Ensures Gruplar' currentPage variable is not reused.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBlPagination function
        bl_pag_match = re.search(
            r'function\s+renderBlPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert bl_pag_match, "renderBlPagination() function not found"
        bl_pag_body = bl_pag_match.group(1)

        # Verify that blCurrentPage is used/assigned within the function
        has_bl_current_page = re.search(
            r'\bblCurrentPage\b',
            bl_pag_body,
            re.IGNORECASE
        )
        assert has_bl_current_page, \
            "renderBlPagination() does not reference blCurrentPage variable (AC-2: isolated state required)"

        # Also verify that #bl-list or .bl-item is used (operates on blacklist rows)
        has_bl_list_ref = re.search(
            r'[#.]bl-list|\.bl-item|querySelectorAll.*bl[-_]item',
            bl_pag_body,
            re.IGNORECASE
        )
        assert has_bl_list_ref, \
            "renderBlPagination() does not reference #bl-list/.bl-item (should target blacklist rows)"

    def test_bl_pagination_uses_acc_button_class(self):
        """
        Given: renderBlPagination(page) function in INDEX_HTML
        When: checking for button styling consistency
        Then: pagination buttons should use `.b-acc` class (same as Gruplar)

        AC-2 (High): Visual consistency with Gruplar pagination buttons.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBlPagination function
        bl_pag_match = re.search(
            r'function\s+renderBlPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert bl_pag_match, "renderBlPagination() function not found"
        bl_pag_body = bl_pag_match.group(1)

        # Check for .b-acc class usage in pagination buttons
        has_acc_class = re.search(
            r'["\']\.b-acc["\']|class\s*=\s*["\'][^"\']*b-acc',
            bl_pag_body,
            re.IGNORECASE
        )
        assert has_acc_class, \
            "renderBlPagination() does not use .b-acc class for buttons (should match Gruplar styling)"

    def test_bl_pagination_uses_arrow_characters(self):
        """
        Given: renderBlPagination(page) function in INDEX_HTML
        When: inspecting button labels/text
        Then: pagination should use `‹` and `›` arrow characters (same as Gruplar)

        AC-2 (High): Visual consistency with Gruplar pagination arrows.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBlPagination function
        bl_pag_match = re.search(
            r'function\s+renderBlPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert bl_pag_match, "renderBlPagination() function not found"
        bl_pag_body = bl_pag_match.group(1)

        # Check for ‹ and › arrow characters
        has_left_arrow = '‹' in bl_pag_body or '&lsaquo;' in bl_pag_body
        has_right_arrow = '›' in bl_pag_body or '&rsaquo;' in bl_pag_body

        assert has_left_arrow and has_right_arrow, \
            "renderBlPagination() does not use ‹/› arrow characters (should match Gruplar)"


class TestBlacklistPaginationVisibility:
    """AC-3: Pagination visibility logic (hide when ≤20 items)"""

    def test_bl_pagination_visibility_logic(self):
        """
        Given: renderBlPagination(page) function in INDEX_HTML
        When: inspecting visibility control logic
        Then: `#bl-pagination` should be hidden when visibleRows.length <= ITEMS_PER_PAGE

        AC-3 (High): Pagination hides automatically for small lists.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBlPagination function
        bl_pag_match = re.search(
            r'function\s+renderBlPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert bl_pag_match, "renderBlPagination() function not found"
        bl_pag_body = bl_pag_match.group(1)

        # Check for visibility control logic
        has_visibility_check = re.search(
            r'(?:display|style\.display)\s*=|\.(?:hidden|hide)|\.style\.display\s*=\s*["\']none',
            bl_pag_body,
            re.IGNORECASE
        )
        assert has_visibility_check, \
            "renderBlPagination() does not contain visibility control (AC-3: should hide pagination for small lists)"

        # More specifically, check for ITEMS_PER_PAGE comparison or length check
        has_length_check = re.search(
            r'(?:visibleRows|\.length)\s*[<>=]+\s*(?:ITEMS_PER_PAGE|\d+)',
            bl_pag_body,
            re.IGNORECASE
        )
        assert has_length_check, \
            "renderBlPagination() does not compare list length to ITEMS_PER_PAGE (AC-3: visibility logic required)"


class TestBlacklistLoadAndRender:
    """AC-4: loadBl() integration with renderBlPagination"""

    def test_loadBl_calls_renderBlPagination(self):
        """
        Given: loadBl() function in INDEX_HTML (async function that loads blacklist)
        When: inspecting its execution flow
        Then: it should call `renderBlPagination(1)` (or equivalent) at the end

        AC-4 (High): After each search/load, pagination must reset to page 1 and re-render.
        """
        html = admin_panel.INDEX_HTML

        # Extract loadBl function
        loadbl_match = re.search(
            r'async\s+function\s+loadBl\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:async\s+)?function|\Z)',
            html,
            re.DOTALL
        )
        assert loadbl_match, "loadBl() function not found in INDEX_HTML"
        loadbl_body = loadbl_match.group(1)

        # Check for renderBlPagination call
        has_render_call = re.search(
            r'\brenderBlPagination\s*\(',
            loadbl_body,
            re.IGNORECASE
        )
        assert has_render_call, \
            "loadBl() does not call renderBlPagination() (AC-4: pagination must be updated after load)"

        # Verify it's called with 1 or similar (page reset)
        has_page_reset = re.search(
            r'\brenderBlPagination\s*\(\s*[01]\s*\)',
            loadbl_body,
            re.IGNORECASE
        )
        assert has_page_reset, \
            "loadBl() does not call renderBlPagination(1) (AC-4: should reset to page 1)"


class TestBlacklistRegressions:
    """Regression tests to ensure other features are not broken"""

    def test_items_per_page_not_redefined(self):
        """
        Regression (Plan.md requirement): ITEMS_PER_PAGE (20) should be defined
        only ONCE globally and SHARED between Gruplar and Kara Liste.

        Given: INDEX_HTML JS section
        When: searching for ITEMS_PER_PAGE constant declarations
        Then: it should appear only once in variable declarations (not redefined per feature)
        """
        html = admin_panel.INDEX_HTML

        # Count ITEMS_PER_PAGE declarations (const/let/var = 20)
        declaration_pattern = r'(?:const|let|var)\s+ITEMS_PER_PAGE\s*=\s*20'
        declarations = re.findall(declaration_pattern, html, re.IGNORECASE)

        assert len(declarations) == 1, \
            f"ITEMS_PER_PAGE defined {len(declarations)} times (should be 1 shared constant, not per-feature)"

    def test_bl_item_class_preserved(self):
        """
        Regression (Plan.md requirement): .bl-item CSS class must still exist
        and be unchanged, as loadBl() uses it to render blacklist items.

        Given: CSS block in INDEX_HTML
        When: searching for .bl-item class definition
        Then: it should be present in the CSS
        """
        html = admin_panel.INDEX_HTML

        # Look for .bl-item class definition in CSS
        has_bl_item_class = re.search(
            r'\.bl-item\s*\{[^}]+\}',
            html,
            re.IGNORECASE
        )
        assert has_bl_item_class or '.bl-item' in html, \
            ".bl-item CSS class definition missing (loadBl() depends on it)"

        # Verify bl-item is still used in loadBl rendering
        loadbl_match = re.search(
            r'async\s+function\s+loadBl\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:async\s+)?function|\Z)',
            html,
            re.DOTALL
        )
        if loadbl_match:
            loadbl_body = loadbl_match.group(1)
            uses_bl_item = re.search(r'bl[-_]item', loadbl_body, re.IGNORECASE)
            assert uses_bl_item, \
                "loadBl() does not reference .bl-item class (regression: list rendering broken)"

    def test_grp_pagination_functions_preserved(self):
        """
        Regression (atdd.md requirement): Gruplar'daki renderGrpPagination,
        currentPage, grpSearchMatches fonksiyon ve değişkenleri untouched kalmalı.

        Given: INDEX_HTML JS section
        When: searching for Gruplar pagination elements
        Then: renderGrpPagination, currentPage, grpSearchMatches should all be present
        """
        html = admin_panel.INDEX_HTML

        # Check for renderGrpPagination function
        has_grp_pag_func = re.search(
            r'function\s+renderGrpPagination\s*\(',
            html,
            re.IGNORECASE
        )
        assert has_grp_pag_func, \
            "renderGrpPagination() function missing (Gruplar pagination broken)"

        # Check for currentPage variable declaration (global)
        has_current_page = re.search(
            r'\bcurrentPage\s*=',
            html,
            re.IGNORECASE
        )
        assert has_current_page, \
            "currentPage variable missing (Gruplar pagination state broken)"

        # Check for grpSearchMatches variable declaration
        has_grp_search = re.search(
            r'\bgrpSearchMatches\s*[=:]',
            html,
            re.IGNORECASE
        )
        assert has_grp_search, \
            "grpSearchMatches variable missing (Gruplar search state broken)"

    def test_blCurrentPage_not_named_currentPage(self):
        """
        Regression (atdd.md risk mitigation): blCurrentPage should NOT be named
        `currentPage` (which belongs to Gruplar), to avoid state collision.

        Given: renderBlPagination function and variable declarations
        When: inspecting for variable naming conflicts
        Then: blCurrentPage should be distinct from currentPage
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBlPagination function
        bl_pag_match = re.search(
            r'function\s+renderBlPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert bl_pag_match, "renderBlPagination() function not found"
        bl_pag_body = bl_pag_match.group(1)

        # Verify blCurrentPage is used (not currentPage in blacklist context)
        has_bl_current_page = re.search(
            r'\bblCurrentPage\b',
            bl_pag_body,
            re.IGNORECASE
        )
        assert has_bl_current_page, \
            "renderBlPagination() does not use blCurrentPage (should use isolated state variable)"

    def test_bl_list_container_exists(self):
        """
        Regression: #bl-list container should still exist (used by loadBl).

        Given: #tab-bl section in INDEX_HTML
        When: checking for list container
        Then: #bl-list should be present
        """
        html = admin_panel.INDEX_HTML

        assert 'id="bl-list"' in html or "id='bl-list'" in html, \
            "#bl-list container missing (loadBl() renders items here)"

    def test_bl_q_search_input_exists(self):
        """
        Regression: #bl-q search input should still exist.

        Given: #tab-bl section in INDEX_HTML
        When: checking for search input
        Then: #bl-q should be present and should trigger loadBl() on input
        """
        html = admin_panel.INDEX_HTML

        # Check for #bl-q input element
        has_bl_q = re.search(
            r'id\s*=\s*["\']bl-q["\']',
            html,
            re.IGNORECASE
        )
        assert has_bl_q, \
            "#bl-q search input missing (AC-4 requires search functionality)"

        # Check that it triggers loadBl on input change
        has_oninput = re.search(
            r'id\s*=\s*["\']bl-q["\'][^>]*oninput\s*=\s*["\']loadBl\(\)',
            html,
            re.IGNORECASE
        )
        assert has_oninput, \
            "#bl-q does not trigger loadBl() on input (search functionality broken)"


class TestBlacklistAndGruplarCoexistence:
    """Cross-feature tests to ensure blacklist and groups work independently"""

    def test_bl_pagination_and_grp_pagination_separate_functions(self):
        """
        Regression (Plan.md risk): renderBlPagination and renderGrpPagination
        should be completely separate functions (different implementations,
        not one calling the other).

        Given: Both renderBlPagination and renderGrpPagination functions
        When: comparing their definitions
        Then: they should not call each other, operate on different DOM elements
        """
        html = admin_panel.INDEX_HTML

        # Extract both functions
        bl_pag_match = re.search(
            r'function\s+renderBlPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        grp_pag_match = re.search(
            r'function\s+renderGrpPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )

        assert bl_pag_match and grp_pag_match, \
            "One or both pagination functions missing"

        bl_pag_body = bl_pag_match.group(1)
        grp_pag_body = grp_pag_match.group(1)

        # Verify bl-pagination targets #bl-list/.bl-item
        bl_targets_bl = re.search(
            r'#bl-list|\.bl-item',
            bl_pag_body,
            re.IGNORECASE
        )
        assert bl_targets_bl, \
            "renderBlPagination() does not target blacklist DOM (#bl-list/.bl-item)"

        # Verify grp-pagination targets #grp-list/.grp-row
        grp_targets_grp = re.search(
            r'#grp-list|\.grp-row',
            grp_pag_body,
            re.IGNORECASE
        )
        assert grp_targets_grp, \
            "renderGrpPagination() does not target groups DOM (#grp-list/.grp-row)"

        # Verify they don't call each other
        bl_calls_grp = re.search(
            r'\brenderGrpPagination\b',
            bl_pag_body,
            re.IGNORECASE
        )
        grp_calls_bl = re.search(
            r'\brenderBlPagination\b',
            grp_pag_body,
            re.IGNORECASE
        )

        assert not bl_calls_grp, \
            "renderBlPagination() should not call renderGrpPagination() (separate implementations)"
        assert not grp_calls_bl, \
            "renderGrpPagination() should not call renderBlPagination() (separate implementations)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
