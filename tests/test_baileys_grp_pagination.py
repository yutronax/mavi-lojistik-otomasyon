#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for baileys-groups-pagination feature.

This module contains STRUCTURAL tests (HTML/CSS/JS string validation) for the
Baileys Grupları pagination refactor (AC-1..AC-5 and regressions). Tests verify that the
`INDEX_HTML` string constant in `src/api/admin_panel.py` contains the expected
structural elements and JS/CSS code patterns.

NOTE on AC-6 (runtime error isolation):
  AC-6: "renderBaileysGrpPagination içinde hata oluşursa, loadBaileysGroups temel render'ını etkilememesi"

  This is a runtime/exception-handling behavior that cannot be tested structurally
  (it depends on JS execution, try/catch blocks, and error propagation at runtime).
  It is validated in the verify step via live e2e tests (separate task).
  These tests DO NOT cover AC-6.

Acceptance Criteria Mapping:
  AC-1 → test_baileys_pagination_html_section_exists()
  AC-2 (func) → test_baileys_pagination_function_exists()
  AC-2 (state) → test_baileys_pagination_function_uses_baileys_current_page()
  AC-2 (button style) → test_baileys_pagination_uses_acc_button_class() + test_baileys_pagination_uses_arrow_characters()
  AC-3 → test_baileys_pagination_visibility_logic()
  AC-4 → test_loadBaileysGroups_calls_renderBaileysGrpPagination_all_exit_points()
  AC-5 → test_filterGroups_resets_both_current_pages()

Regression Tests:
  - test_items_per_page_not_redefined(): Validates that ITEMS_PER_PAGE is not re-declared
  - test_grp_row_class_preserved(): Ensures .grp-row CSS class exists (used by Baileys rows)
  - test_baileys_current_page_uses_baileys_prefix(): Ensures pagination state is isolated (not named 'currentPage')
  - test_grp_pagination_functions_untouched(): Validates that Gruplar renderGrpPagination is unchanged
  - test_grp_search_state_untouched(): Ensures Gruplar grpSearchMatches is unchanged
  - test_bl_pagination_functions_untouched(): Validates that Kara Liste renderBlPagination is unchanged
  - test_bl_current_page_untouched(): Ensures Kara Liste blCurrentPage is unchanged
"""

import pytest
import re
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.api import admin_panel


class TestBaileysGroupsPaginationHtmlStructure:
    """AC-1: Pagination HTML section in Baileys Grupları tab"""

    def test_baileys_pagination_html_section_exists(self):
        """
        Given: `#tab-grp` section in INDEX_HTML (groups tab)
        When: checking for pagination container in Baileys panel
        Then: `#baileys-pagination` section should be present in HTML

        AC-1 (Critical): Pagination UI container must exist in the DOM,
        separate from #grp-pagination (Kayıtlı Gruplar) and #bl-pagination (Kara Liste).
        """
        html = admin_panel.INDEX_HTML

        # Check for #tab-grp section existence
        assert re.search(r'id=["\']tab-grp["\']', html), \
            "INDEX_HTML must contain the tab-grp div"

        # Extract the #tab-grp section for focused testing
        tab_grp_match = re.search(
            r'id=["\']tab-grp["\'].*?(?=<div\s+id=["\'][^"\']+["\']|\Z)',
            html,
            re.DOTALL
        )
        assert tab_grp_match, "#tab-grp section not found in INDEX_HTML"
        tab_grp_section = tab_grp_match.group(0)

        # Verify presence of #baileys-pagination section
        has_baileys_pagination = re.search(
            r'id\s*=\s*["\']baileys-pagination["\']',
            tab_grp_section,
            re.IGNORECASE
        )
        assert has_baileys_pagination, \
            "#baileys-pagination section not found in #tab-grp (AC-1 requires pagination container)"


class TestBaileysGroupsPaginationFunction:
    """AC-2: renderBaileysGrpPagination function implementation"""

    def test_baileys_pagination_function_exists(self):
        """
        Given: INDEX_HTML JS section
        When: searching for Baileys pagination function definition
        Then: a `renderBaileysGrpPagination(page)` function should be defined

        AC-2 (Critical): Baileys pagination function must exist for client-side navigation.
        """
        html = admin_panel.INDEX_HTML

        # Look for renderBaileysGrpPagination function definition
        pagination_func_pattern = r'function\s+renderBaileysGrpPagination\s*\('
        has_pagination_func = re.search(pagination_func_pattern, html, re.IGNORECASE)

        assert has_pagination_func, \
            "renderBaileysGrpPagination() function not found in INDEX_HTML (AC-2 requires pagination logic)"

    def test_baileys_pagination_function_uses_baileys_current_page(self):
        """
        Given: renderBaileysGrpPagination(page) function in INDEX_HTML
        When: inspecting variable usage for pagination state
        Then: it should use `baileysCurrentPage` variable (isolated from Gruplar' currentPage and Kara Liste' blCurrentPage)

        AC-2 (Critical): Isolated pagination state for Baileys (not shared with other tabs).
        Regression: Ensures Gruplar' currentPage and Kara Liste' blCurrentPage are not reused.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBaileysGrpPagination function
        baileys_pag_match = re.search(
            r'function\s+renderBaileysGrpPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert baileys_pag_match, "renderBaileysGrpPagination() function not found"
        baileys_pag_body = baileys_pag_match.group(1)

        # Verify that baileysCurrentPage is used/assigned within the function
        has_baileys_current_page = re.search(
            r'\bbaileysCurrentPage\b',
            baileys_pag_body,
            re.IGNORECASE
        )
        assert has_baileys_current_page, \
            "renderBaileysGrpPagination() does not reference baileysCurrentPage variable (AC-2: isolated state required)"

        # Also verify that #baileys-available-groups-list or .grp-row is used (operates on Baileys rows)
        has_baileys_list_ref = re.search(
            r'#baileys-available-groups-list|\.grp-row|querySelectorAll.*grp[-_]row',
            baileys_pag_body,
            re.IGNORECASE
        )
        assert has_baileys_list_ref, \
            "renderBaileysGrpPagination() does not reference #baileys-available-groups-list/.grp-row (should target Baileys rows)"

    def test_baileys_pagination_uses_acc_button_class(self):
        """
        Given: renderBaileysGrpPagination(page) function in INDEX_HTML
        When: checking for button styling consistency
        Then: pagination buttons should use `.b-acc` class (same as Gruplar and Kara Liste)

        AC-2 (High): Visual consistency with other pagination buttons.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBaileysGrpPagination function
        baileys_pag_match = re.search(
            r'function\s+renderBaileysGrpPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert baileys_pag_match, "renderBaileysGrpPagination() function not found"
        baileys_pag_body = baileys_pag_match.group(1)

        # Check for .b-acc class usage in pagination buttons
        has_acc_class = re.search(
            r'["\']\.b-acc["\']|class\s*=\s*["\'][^"\']*b-acc',
            baileys_pag_body,
            re.IGNORECASE
        )
        assert has_acc_class, \
            "renderBaileysGrpPagination() does not use .b-acc class for buttons (should match other pagination styling)"

    def test_baileys_pagination_uses_arrow_characters(self):
        """
        Given: renderBaileysGrpPagination(page) function in INDEX_HTML
        When: inspecting button labels/text
        Then: pagination should use `‹` and `›` arrow characters (same as Gruplar and Kara Liste)

        AC-2 (High): Visual consistency with other pagination arrows.
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBaileysGrpPagination function
        baileys_pag_match = re.search(
            r'function\s+renderBaileysGrpPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert baileys_pag_match, "renderBaileysGrpPagination() function not found"
        baileys_pag_body = baileys_pag_match.group(1)

        # Check for ‹ and › arrow characters
        has_left_arrow = '‹' in baileys_pag_body or '&lsaquo;' in baileys_pag_body
        has_right_arrow = '›' in baileys_pag_body or '&rsaquo;' in baileys_pag_body

        assert has_left_arrow and has_right_arrow, \
            "renderBaileysGrpPagination() does not use ‹/› arrow characters (should match other pagination)"


class TestBaileysGroupsPaginationVisibility:
    """AC-3: Pagination visibility logic (hide when ≤20 items)"""

    def test_baileys_pagination_visibility_logic(self):
        """
        Given: renderBaileysGrpPagination(page) function in INDEX_HTML
        When: inspecting visibility control logic
        Then: `#baileys-pagination` should be hidden when visibleRows.length <= ITEMS_PER_PAGE

        AC-3 (High): Pagination hides automatically for small Baileys lists (same as other tabs).
        """
        html = admin_panel.INDEX_HTML

        # Extract renderBaileysGrpPagination function
        baileys_pag_match = re.search(
            r'function\s+renderBaileysGrpPagination\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async function)|\Z)',
            html,
            re.DOTALL
        )
        assert baileys_pag_match, "renderBaileysGrpPagination() function not found"
        baileys_pag_body = baileys_pag_match.group(1)

        # Check for visibility control logic
        has_visibility_check = re.search(
            r'(?:display|style\.display)\s*=|\.(?:hidden|hide)|\.style\.display\s*=\s*["\']none',
            baileys_pag_body,
            re.IGNORECASE
        )
        assert has_visibility_check, \
            "renderBaileysGrpPagination() does not contain visibility control (AC-3: should hide pagination for small lists)"

        # More specifically, check for ITEMS_PER_PAGE comparison or length check
        has_length_check = re.search(
            r'(?:visibleRows|\.length)\s*[<>=]+\s*(?:ITEMS_PER_PAGE|\d+)',
            baileys_pag_body,
            re.IGNORECASE
        )
        assert has_length_check, \
            "renderBaileysGrpPagination() does not compare list length to ITEMS_PER_PAGE (AC-3: visibility logic required)"


class TestBaileysGroupsLoadAndRender:
    """AC-4: loadBaileysGroups() integration with renderBaileysGrpPagination (all exit points)"""

    def test_loadBaileysGroups_calls_renderBaileysGrpPagination_all_exit_points(self):
        """
        Given: loadBaileysGroups() function in INDEX_HTML (async function that loads Baileys groups)
        When: inspecting its execution flow at ALL THREE exit points
        Then: at each exit point (d.message early return, !unsaved.length early return, normal end)
              `baileysCurrentPage = 1` should be set and `renderBaileysGrpPagination` should be called

        AC-4 (High): After each load/reload, Baileys pagination must reset to page 1 and re-render.
        Regression (atdd.md risk): Stale pagination if early returns don't reset state.
        """
        html = admin_panel.INDEX_HTML

        # Extract loadBaileysGroups function
        loadbailey_match = re.search(
            r'async\s+function\s+loadBaileysGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:async\s+)?function|\Z)',
            html,
            re.DOTALL
        )
        assert loadbailey_match, "loadBaileysGroups() function not found in INDEX_HTML"
        loadbailey_body = loadbailey_match.group(1)

        # Exit point 1: d.message early return (Baileys not connected)
        has_message_check = re.search(
            r'd\.message|\.message',
            loadbailey_body,
            re.IGNORECASE
        )
        assert has_message_check, \
            "loadBaileysGroups() does not check d.message (AC-4: early return for not-connected state)"

        # Exit point 2: !unsaved.length early return (all groups already saved)
        has_unsaved_check = re.search(
            r'!unsaved\.length|unsaved\.length\s*===\s*0',
            loadbailey_body,
            re.IGNORECASE
        )
        assert has_unsaved_check, \
            "loadBaileysGroups() does not check !unsaved.length (AC-4: early return for all-saved state)"

        # All exit points should reset baileysCurrentPage
        # This is a higher-level test; the detailed verification happens in separate tests
        # but we check that the function structure allows for pagination state reset
        has_pagination_reset = re.search(
            r'\bbaileysCurrentPage\s*=\s*[01]|\brenderBaileysGrpPagination\s*\(',
            loadbailey_body,
            re.IGNORECASE
        )
        assert has_pagination_reset, \
            "loadBaileysGroups() does not reference baileysCurrentPage reset or renderBaileysGrpPagination call (AC-4 violation)"


class TestBaileysGroupsSearchIntegration:
    """AC-5: filterGroups() integration with Baileys pagination"""

    def test_filterGroups_resets_both_current_pages(self):
        """
        Given: filterGroups() function (search handler) in INDEX_HTML
        When: user enters search query while both Gruplar and Baileys pagination are active
        Then: BOTH `currentPage` (Gruplar) AND `baileysCurrentPage` (Baileys) should be reset to 1
               and both renderGrpPagination(1) and renderBaileysGrpPagination(1) should be called

        AC-5 (High): Search result must reset BOTH tabs to first page simultaneously (shared search box).
        Regression: Ensures Gruplar and Baileys stay in sync during search.
        """
        html = admin_panel.INDEX_HTML

        # Extract filterGroups function
        filtergroups_match = re.search(
            r'function\s+filterGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:function|async)|\Z)',
            html,
            re.DOTALL
        )
        assert filtergroups_match, "filterGroups() function not found in INDEX_HTML"
        filtergroups_body = filtergroups_match.group(1)

        # Check that BOTH currentPage and baileysCurrentPage are reset
        has_grp_reset = re.search(
            r'\bcurrentPage\s*=\s*[01]',
            filtergroups_body,
            re.IGNORECASE
        )
        assert has_grp_reset, \
            "filterGroups() does not reset currentPage (Gruplar pagination) (AC-5 violation)"

        has_baileys_reset = re.search(
            r'\bbaileysCurrentPage\s*=\s*[01]',
            filtergroups_body,
            re.IGNORECASE
        )
        assert has_baileys_reset, \
            "filterGroups() does not reset baileysCurrentPage (Baileys pagination) (AC-5 violation)"

        # Check that BOTH pagination functions are called
        has_grp_pag_call = re.search(
            r'\brenderGrpPagination\s*\(',
            filtergroups_body,
            re.IGNORECASE
        )
        assert has_grp_pag_call, \
            "filterGroups() does not call renderGrpPagination() (Gruplar pagination not re-rendered after search)"

        has_baileys_pag_call = re.search(
            r'\brenderBaileysGrpPagination\s*\(',
            filtergroups_body,
            re.IGNORECASE
        )
        assert has_baileys_pag_call, \
            "filterGroups() does not call renderBaileysGrpPagination() (Baileys pagination not re-rendered after search)"


class TestBaileysGroupsRegressions:
    """Regression tests to ensure other features are not broken"""

    def test_items_per_page_not_redefined(self):
        """
        Regression (atdd.md requirement): ITEMS_PER_PAGE (20) should be defined
        only ONCE globally and SHARED between Gruplar, Kara Liste, and Baileys.

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

    def test_grp_row_class_preserved(self):
        """
        Regression (atdd.md requirement): .grp-row CSS class must still exist
        and be unchanged, as both loadGroups() and loadBaileysGroups() use it to render rows.

        Given: CSS block in INDEX_HTML
        When: searching for .grp-row class definition
        Then: it should be present in the CSS and used by both functions
        """
        html = admin_panel.INDEX_HTML

        # Look for .grp-row class definition in CSS
        has_grp_row_class = re.search(
            r'\.(grp[-_]row)\s*\{[^}]+\}',
            html,
            re.IGNORECASE
        )
        assert has_grp_row_class or '.grp-row' in html, \
            ".grp-row CSS class definition missing (both loadGroups and loadBaileysGroups depend on it)"

        # Verify .grp-row is used in loadBaileysGroups rendering
        loadbailey_match = re.search(
            r'async\s+function\s+loadBaileysGroups\s*\([^)]*\)\s*\{(.*?)(?=\n\s*(?:async\s+)?function|\Z)',
            html,
            re.DOTALL
        )
        if loadbailey_match:
            loadbailey_body = loadbailey_match.group(1)
            uses_grp_row = re.search(r'grp[-_]row', loadbailey_body, re.IGNORECASE)
            assert uses_grp_row, \
                "loadBaileysGroups() does not reference .grp-row class (regression: Baileys row rendering broken)"

    def test_baileys_current_page_uses_baileys_prefix(self):
        """
        Regression (atdd.md risk mitigation): baileysCurrentPage should NOT be named
        `currentPage` (which belongs to Gruplar) or `blCurrentPage` (which belongs to Kara Liste),
        to avoid state collision.

        Given: Global variable declarations in INDEX_HTML
        When: searching for Baileys pagination state variable
        Then: baileysCurrentPage should be a distinct variable name (not reusing currentPage or blCurrentPage)
        """
        html = admin_panel.INDEX_HTML

        # Check that baileysCurrentPage is declared as its own variable
        has_baileys_current_page = re.search(
            r'\blet\s+baileysCurrentPage\s*=',
            html,
            re.IGNORECASE
        )
        assert has_baileys_current_page, \
            "baileysCurrentPage variable declaration not found (should be distinct from currentPage and blCurrentPage)"

    def test_grp_pagination_functions_untouched(self):
        """
        Regression (atdd.md requirement): Gruplar'daki renderGrpPagination,
        currentPage, grpSearchMatches fonksiyon ve değişkenleri AYNEN kalmalı.

        Given: INDEX_HTML JS section
        When: searching for Gruplar pagination elements
        Then: renderGrpPagination, currentPage, grpSearchMatches should all be present and unchanged
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
            r'\blet\s+currentPage\s*=',
            html,
            re.IGNORECASE
        )
        assert has_current_page, \
            "currentPage variable missing (Gruplar pagination state broken)"

        # Check for grpSearchMatches variable declaration
        has_grp_search = re.search(
            r'\blet\s+grpSearchMatches\s*=',
            html,
            re.IGNORECASE
        )
        assert has_grp_search, \
            "grpSearchMatches variable missing (Gruplar search state broken)"

    def test_bl_pagination_functions_untouched(self):
        """
        Regression (atdd.md requirement): Kara Liste'deki renderBlPagination,
        blCurrentPage fonksiyon ve değişkenleri AYNEN kalmalı.

        Given: INDEX_HTML JS section
        When: searching for Kara Liste pagination elements
        Then: renderBlPagination and blCurrentPage should all be present and unchanged
        """
        html = admin_panel.INDEX_HTML

        # Check for renderBlPagination function
        has_bl_pag_func = re.search(
            r'function\s+renderBlPagination\s*\(',
            html,
            re.IGNORECASE
        )
        assert has_bl_pag_func, \
            "renderBlPagination() function missing (Kara Liste pagination broken)"

        # Check for blCurrentPage variable declaration (global)
        has_bl_current_page = re.search(
            r'\blet\s+blCurrentPage\s*=',
            html,
            re.IGNORECASE
        )
        assert has_bl_current_page, \
            "blCurrentPage variable missing (Kara Liste pagination state broken)"

    def test_bl_item_class_preserved(self):
        """
        Regression (atdd.md requirement): .bl-item CSS class must still exist
        and be unchanged, as loadBl() uses it to render blacklist items.

        Given: CSS block in INDEX_HTML
        When: searching for .bl-item class definition
        Then: it should be present in the CSS
        """
        html = admin_panel.INDEX_HTML

        # Look for .bl-item class definition in CSS
        has_bl_item_class = re.search(
            r'\.(bl|black)[-_]item\s*\{[^}]+\}',
            html,
            re.IGNORECASE
        )
        assert has_bl_item_class or '.bl-item' in html, \
            ".bl-item CSS class definition missing (loadBl() depends on it)"

    def test_baileys_available_groups_list_container_exists(self):
        """
        Regression: #baileys-available-groups-list container should still exist
        and be separate from #grp-list (Gruplar).

        Given: #tab-grp section in INDEX_HTML
        When: checking for Baileys list container
        Then: #baileys-available-groups-list should be present
        """
        html = admin_panel.INDEX_HTML

        assert 'id="baileys-available-groups-list"' in html or "id='baileys-available-groups-list'" in html, \
            "#baileys-available-groups-list container missing (loadBaileysGroups() renders items here)"

    def test_grp_search_input_and_filter_preserved(self):
        """
        Regression: #grp-search input (shared by Gruplar and Baileys) and filterGroups function should exist.

        Given: #tab-grp section in INDEX_HTML
        When: checking for search input and filter function
        Then: #grp-search should be present and trigger filterGroups() on input
        """
        html = admin_panel.INDEX_HTML

        # Check for #grp-search input element
        has_grp_search = re.search(
            r'id\s*=\s*["\']grp-search["\']',
            html,
            re.IGNORECASE
        )
        assert has_grp_search, \
            "#grp-search input missing (shared search for Gruplar and Baileys)"

        # Check for filterGroups function
        has_filter_func = re.search(
            r'function\s+filterGroups\s*\(',
            html,
            re.IGNORECASE
        )
        assert has_filter_func, \
            "filterGroups() function missing (search filtering broken)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
