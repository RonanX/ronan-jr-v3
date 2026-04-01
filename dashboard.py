"""
Ronan Jr v3 - Surgical Dashboard
Real-time SQLite database editor for character and move management
"""

import customtkinter as ctk
import sqlite3
import json
from tkinter import messagebox, simpledialog

# Configure appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DATABASE_PATH = "database/ronan.db"


class RonanDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("Ronan Jr v3 - Surgical Dashboard")
        self.geometry("1400x900")

        # State
        self.current_character = None
        self.current_move = None
        self.current_move_form = None  # Track form for multi-form characters
        self.current_form = None  # For forms tab
        self.current_deployable = None  # For deployables tab
        self.conn = None
        self.cursor = None

        # Connect to database
        self.connect_database()

        # Build UI
        self.build_ui()

        # Load initial data
        self.refresh_character_list()

    def connect_database(self):
        """Connect to SQLite database"""
        try:
            self.conn = sqlite3.connect(DATABASE_PATH)
            self.cursor = self.conn.cursor()
            print(f"[OK] Connected to {DATABASE_PATH}")
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to connect to database:\n{e}")
            self.quit()

    def safe_int(self, value, default=0):
        """Safely parse integer from string, return default if invalid or empty"""
        if not value or str(value).strip() == "":
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def build_ui(self):
        """Build the main UI layout"""
        # Configure grid layout (2 columns: sidebar, main content)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===== LEFT SIDEBAR =====
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(1, weight=1)

        # Sidebar title
        self.sidebar_title = ctk.CTkLabel(
            self.sidebar,
            text="Characters",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.sidebar_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Character list (scrollable)
        self.character_list_frame = ctk.CTkScrollableFrame(self.sidebar, label_text="")
        self.character_list_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Rename button
        self.rename_btn = ctk.CTkButton(
            self.sidebar,
            text="✏️ Rename",
            command=self.rename_character,
            fg_color="darkorange",
            hover_color="orange"
        )
        self.rename_btn.grid(row=2, column=0, padx=10, pady=10)

        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            self.sidebar,
            text="🔄 Refresh List",
            command=self.refresh_character_list
        )
        self.refresh_btn.grid(row=3, column=0, padx=10, pady=10)

        # ===== MAIN CONTENT AREA =====
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Main title
        self.main_title = ctk.CTkLabel(
            self.main_frame,
            text="Select a character",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.main_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Tab view
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        # Add tabs
        self.tabview.add("Core Stats")
        self.tabview.add("Attributes")
        self.tabview.add("Moves")
        self.tabview.add("Forms")
        self.tabview.add("Deployables")
        self.tabview.add("DM Screen")

        # CRITICAL: Create status_label and save_btn BEFORE building tabs
        # (tabs may call set_status() during initialization)
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=2, column=0, padx=20, pady=(5, 10))

        # Save button
        self.save_btn = ctk.CTkButton(
            self.main_frame,
            text="💾 SAVE CHANGES TO DATABASE",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            command=self.save_changes
        )
        self.save_btn.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")

        # Build tab contents (AFTER status_label exists)
        self.build_core_stats_tab()
        self.build_attributes_tab()
        self.build_moves_tab()
        self.build_forms_tab()
        self.build_deployables_tab()
        self.build_dm_screen_tab()

    def build_core_stats_tab(self):
        """Build Core Stats tab"""
        tab = self.tabview.tab("Core Stats")

        # Create entry fields for core stats
        self.core_entries = {}

        stats = [
            ("HP", "hp"),
            ("Max HP", "max_hp"),
            ("MP", "mp"),
            ("Max MP", "max_mp"),
            ("AC Tier (1-3)", "ac"),
            ("Current Stars", "current_stars"),
            ("Max Stars", "max_stars"),
            ("Proficiency", "proficiency")
        ]

        for i, (label, key) in enumerate(stats):
            row_frame = ctk.CTkFrame(tab, fg_color="transparent")
            row_frame.grid(row=i, column=0, padx=20, pady=10, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            lbl = ctk.CTkLabel(row_frame, text=label, width=150, anchor="w")
            lbl.grid(row=0, column=0, padx=(0, 10))

            entry = ctk.CTkEntry(row_frame, placeholder_text=label)
            entry.grid(row=0, column=1, sticky="ew")

            self.core_entries[key] = entry

    def build_attributes_tab(self):
        """Build Attributes tab (JSON handling for base_stats)"""
        tab = self.tabview.tab("Attributes")

        # Info label
        info = ctk.CTkLabel(
            tab,
            text="Character Attributes (stored as JSON in base_stats)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        info.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Create entry fields for attributes
        self.attr_entries = {}

        attributes = ["str", "dex", "con", "int", "wis", "cha"]

        for i, attr in enumerate(attributes):
            row_frame = ctk.CTkFrame(tab, fg_color="transparent")
            row_frame.grid(row=i+1, column=0, padx=20, pady=10, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            lbl = ctk.CTkLabel(row_frame, text=attr.upper(), width=150, anchor="w")
            lbl.grid(row=0, column=0, padx=(0, 10))

            entry = ctk.CTkEntry(row_frame, placeholder_text=attr.upper())
            entry.grid(row=0, column=1, sticky="ew")

            self.attr_entries[attr] = entry

    def build_moves_tab(self):
        """Build Moves tab (surgical suite for move editing)"""
        tab = self.tabview.tab("Moves")

        # Move selector dropdown with add/delete buttons
        selector_frame = ctk.CTkFrame(tab, fg_color="transparent")
        selector_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        selector_frame.grid_columnconfigure(1, weight=1)

        lbl = ctk.CTkLabel(selector_frame, text="Select Move:", width=150, anchor="w")
        lbl.grid(row=0, column=0, padx=(0, 10))

        self.move_selector = ctk.CTkOptionMenu(
            selector_frame,
            values=["No moves available"],
            command=self.load_move_data
        )
        self.move_selector.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        # Add/Rename/Delete buttons
        add_btn = ctk.CTkButton(
            selector_frame,
            text="➕ Add",
            width=70,
            command=self.add_move
        )
        add_btn.grid(row=0, column=2, padx=5)

        rename_move_btn = ctk.CTkButton(
            selector_frame,
            text="✏️ Rename",
            width=70,
            fg_color="darkorange",
            hover_color="orange",
            command=self.rename_move
        )
        rename_move_btn.grid(row=0, column=3, padx=5)

        bulk_del_btn = ctk.CTkButton(
            selector_frame,
            text="🗑️ Bulk Delete",
            width=100,
            fg_color="darkred",
            hover_color="red",
            command=self.bulk_delete_moves
        )
        bulk_del_btn.grid(row=0, column=4, padx=5)

        # Scrollable content frame for all move parameters
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Move parameter fields
        self.move_entries = {}

        move_params = [
            ("Form Name", "form_name"),
            ("Damage", "damage"),
            ("Hits", "hits"),
            ("MP Cost", "mp_cost"),
            ("HP Cost", "hp_cost"),
            ("Star Cost", "star_cost"),
            ("Stat (str/dex/etc)", "stat"),
            ("Bonus On Hit", "bonus_on_hit"),
            ("Save Effect", "save_effect"),
            ("Self Effect (Guaranteed)", "self_effect"),
            ("Target Effect (Guaranteed)", "target_effect"),
            ("Current Uses", "uses"),
            ("Max Uses (Slots)", "max_uses"),
            ("Duration (Rounds)", "duration"),
            ("Cooldown (Rounds)", "cooldown")
        ]

        for i, (label, key) in enumerate(move_params):
            row_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            row_frame.grid(row=i, column=0, padx=20, pady=10, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            lbl = ctk.CTkLabel(row_frame, text=label, width=150, anchor="w")
            lbl.grid(row=0, column=0, padx=(0, 10))

            entry = ctk.CTkEntry(row_frame, placeholder_text=label)
            entry.grid(row=0, column=1, sticky="ew")

            self.move_entries[key] = entry

        # Description field (textbox for multi-line)
        desc_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        desc_frame.grid(row=len(move_params), column=0, padx=20, pady=10, sticky="ew")
        desc_frame.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(desc_frame, text="Description:", anchor="w")
        lbl.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.move_description = ctk.CTkTextbox(desc_frame, height=60)
        self.move_description.grid(row=1, column=0, sticky="ew")

        # Add the info button for the effect syntax
        info_btn = ctk.CTkButton(
            scroll_frame,
            text="ℹ️ Effect Syntax Guide",
            width=150,
            fg_color="transparent",
            border_width=1,
            command=lambda: messagebox.showinfo(
                "Effect Syntax",
                "Format for Bonus On Hit / Save Effect:\n\n"
                "name:duration:note\n\n"
                "Examples:\n"
                "• stunned  (defaults to 2 rounds)\n"
                "• blinded:1  (blinded for 1 round)\n"
                "• dot:3:acid  (DoT for 3 rounds, labeled 'acid')\n\n"
                "Valid Names:\n"
                "dot, hp_mod, mp_mod, stat_mod, cover, blinded, slowed, stunned, advantage, disadvantage"
            )
        )
        info_btn.grid(row=len(move_params)+1, column=0, padx=20, pady=(0, 10), sticky="w")

    def build_forms_tab(self):
        """Build Forms tab for transformation management"""
        tab = self.tabview.tab("Forms")

        # Info label
        info = ctk.CTkLabel(
            tab,
            text="Character Transformations",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        info.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Form selector dropdown with add/delete buttons
        selector_frame = ctk.CTkFrame(tab, fg_color="transparent")
        selector_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        selector_frame.grid_columnconfigure(1, weight=1)

        lbl = ctk.CTkLabel(selector_frame, text="Select Form:", width=150, anchor="w")
        lbl.grid(row=0, column=0, padx=(0, 10))

        self.form_selector = ctk.CTkOptionMenu(
            selector_frame,
            values=["No forms available"],
            command=self.load_form_data
        )
        self.form_selector.grid(row=0, column=1, sticky="ew", padx=(0, 5))

        # Add/Rename/Delete buttons
        add_form_btn = ctk.CTkButton(
            selector_frame,
            text="➕ Add",
            width=70,
            command=self.add_form
        )
        add_form_btn.grid(row=0, column=2, padx=5)

        rename_form_btn = ctk.CTkButton(
            selector_frame,
            text="✏️ Rename",
            width=70,
            fg_color="darkorange",
            hover_color="orange",
            command=self.rename_form
        )
        rename_form_btn.grid(row=0, column=3, padx=5)

        del_form_btn = ctk.CTkButton(
            selector_frame,
            text="🗑️ Delete",
            width=70,
            fg_color="darkred",
            hover_color="red",
            command=self.delete_form
        )
        del_form_btn.grid(row=0, column=4, padx=5)

        # Form parameter fields
        self.form_entries = {}

        form_params = [
            ("AC", "ac"),
            ("Transformation Cost", "transformation_cost"),
            ("Duration", "duration"),
            ("Cancellable (0 or 1)", "cancellable"),
            ("DoT Damage", "dot_damage"),
            ("DoT Type", "dot_type")
        ]

        for i, (label, key) in enumerate(form_params):
            row_frame = ctk.CTkFrame(tab, fg_color="transparent")
            row_frame.grid(row=i+2, column=0, padx=20, pady=10, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            lbl = ctk.CTkLabel(row_frame, text=label, width=150, anchor="w")
            lbl.grid(row=0, column=0, padx=(0, 10))

            entry = ctk.CTkEntry(row_frame, placeholder_text=label)
            entry.grid(row=0, column=1, sticky="ew")

            self.form_entries[key] = entry

        # Stats JSON text box
        stats_json_frame = ctk.CTkFrame(tab, fg_color="transparent")
        stats_json_frame.grid(row=8, column=0, padx=20, pady=10, sticky="ew")
        stats_json_frame.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(stats_json_frame, text="Stats JSON (raw):", anchor="w")
        lbl.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.form_stats_json = ctk.CTkTextbox(stats_json_frame, height=100)
        self.form_stats_json.grid(row=1, column=0, sticky="ew")

    def build_deployables_tab(self):
        """Build Deployables tab"""
        tab = self.tabview.tab("Deployables")

        # Info label
        info = ctk.CTkLabel(
            tab,
            text="Deployables (owned by current character)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        info.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Deployable selector dropdown
        selector_frame = ctk.CTkFrame(tab, fg_color="transparent")
        selector_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        selector_frame.grid_columnconfigure(1, weight=1)

        lbl = ctk.CTkLabel(selector_frame, text="Select Deployable:", width=150, anchor="w")
        lbl.grid(row=0, column=0, padx=(0, 10))

        self.deployable_selector = ctk.CTkOptionMenu(
            selector_frame,
            values=["No deployables available"],
            command=self.load_deployable_data
        )
        self.deployable_selector.grid(row=0, column=1, sticky="ew")

        # Deployable parameter fields
        self.deployable_entries = {}

        deployable_params = [
            ("HP", "hp"),
            ("Max HP", "max_hp"),
            ("AC", "ac"),
            ("Duration (rounds)", "duration"),
            ("Stars", "stars"),
            ("Max Stars", "max_stars")
        ]

        for i, (label, key) in enumerate(deployable_params):
            row_frame = ctk.CTkFrame(tab, fg_color="transparent")
            row_frame.grid(row=i+2, column=0, padx=20, pady=10, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            lbl = ctk.CTkLabel(row_frame, text=label, width=150, anchor="w")
            lbl.grid(row=0, column=0, padx=(0, 10))

            entry = ctk.CTkEntry(row_frame, placeholder_text=label)
            entry.grid(row=0, column=1, sticky="ew")

            self.deployable_entries[key] = entry

    def build_dm_screen_tab(self):
        """Build DM Screen tab (global combat state viewer)"""
        tab = self.tabview.tab("DM Screen")

        # Info label
        info = ctk.CTkLabel(
            tab,
            text="DM Screen - Global Combat State (NOT character-specific)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        info.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Initiative section
        init_frame = ctk.CTkFrame(tab, fg_color="transparent")
        init_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        init_label = ctk.CTkLabel(init_frame, text="Current Round:", font=ctk.CTkFont(size=12, weight="bold"))
        init_label.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.current_round_label = ctk.CTkLabel(init_frame, text="--", font=ctk.CTkFont(size=12))
        self.current_round_label.grid(row=0, column=1, sticky="w")

        # Refresh button
        refresh_dm_btn = ctk.CTkButton(
            tab,
            text="🔄 Refresh Effects",
            command=self.refresh_dm_screen,
            width=150
        )
        refresh_dm_btn.grid(row=2, column=0, padx=20, pady=10, sticky="w")

        # Effects list (scrollable)
        effects_label = ctk.CTkLabel(
            tab,
            text="Active Effects:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        effects_label.grid(row=3, column=0, padx=20, pady=(10, 5), sticky="w")

        self.effects_scroll_frame = ctk.CTkScrollableFrame(tab, height=400)
        self.effects_scroll_frame.grid(row=4, column=0, padx=20, pady=10, sticky="nsew")
        tab.grid_rowconfigure(4, weight=1)

        # Load initial data
        self.refresh_dm_screen()

    def refresh_dm_screen(self):
        """Refresh the DM Screen with current initiative and effects"""
        try:
            # Get current round from initiative (actual column name is round_number)
            self.cursor.execute("SELECT round_number FROM initiative WHERE id = 1")
            round_row = self.cursor.fetchone()
            current_round = round_row[0] if round_row else 0
            self.current_round_label.configure(text=str(current_round))

            # Clear effects frame
            for widget in self.effects_scroll_frame.winfo_children():
                widget.destroy()

            # Get all active effects
            self.cursor.execute("""
                SELECT id, character_name, effect_name, expires_at_round
                FROM effects
                ORDER BY expires_at_round, character_name, effect_name
            """)

            effects = self.cursor.fetchall()

            if not effects:
                no_effects_label = ctk.CTkLabel(
                    self.effects_scroll_frame,
                    text="No active effects",
                    font=ctk.CTkFont(size=12, style="italic")
                )
                no_effects_label.pack(pady=20)
            else:
                # Display each effect with a kill button
                for effect_id, char_name, effect_name, expires_at_round in effects:
                    effect_frame = ctk.CTkFrame(self.effects_scroll_frame, fg_color="transparent")
                    effect_frame.pack(pady=5, padx=10, fill="x")

                    # Effect text
                    effect_text = f"[Round {expires_at_round}] {char_name} - {effect_name}"
                    effect_label = ctk.CTkLabel(
                        effect_frame,
                        text=effect_text,
                        anchor="w"
                    )
                    effect_label.pack(side="left", fill="x", expand=True)

                    # Kill button
                    kill_btn = ctk.CTkButton(
                        effect_frame,
                        text="❌",
                        width=30,
                        fg_color="darkred",
                        hover_color="red",
                        command=lambda eid=effect_id: self.kill_effect(eid)
                    )
                    kill_btn.pack(side="right")

            self.set_status(f"DM Screen refreshed - Round {current_round}, {len(effects)} effect(s)", "success")

        except Exception as e:
            self.set_status(f"Error refreshing DM screen: {e}", "error")

    def kill_effect(self, effect_id):
        """Delete a specific effect by ID and refresh the DM screen"""
        try:
            self.cursor.execute("DELETE FROM effects WHERE id = ?", (effect_id,))
            self.conn.commit()
            self.refresh_dm_screen()
            self.set_status(f"Killed effect #{effect_id}", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error killing effect: {e}", "error")
            messagebox.showerror("Error", f"Failed to delete effect:\n{e}")

    def refresh_character_list(self):
        """Refresh the character list from database"""
        try:
            # Clear existing buttons
            for widget in self.character_list_frame.winfo_children():
                widget.destroy()

            # Query characters
            self.cursor.execute("SELECT name FROM characters ORDER BY name")
            characters = self.cursor.fetchall()

            # Create button for each character
            for (name,) in characters:
                btn = ctk.CTkButton(
                    self.character_list_frame,
                    text=name,
                    command=lambda n=name: self.select_character(n)
                )
                btn.pack(pady=5, padx=10, fill="x")

            self.set_status(f"Loaded {len(characters)} characters", "success")

        except Exception as e:
            self.set_status(f"Error loading characters: {e}", "error")

    def rename_character(self):
        """Rename the currently selected character (updates ALL foreign keys)"""
        if not self.current_character:
            messagebox.showerror("Error", "No character selected!")
            return

        # Prompt for new name
        new_name = simpledialog.askstring("Rename Character", f"Rename '{self.current_character}' to:", initialvalue=self.current_character)
        if not new_name or new_name == self.current_character:
            return

        # Confirm rename
        confirm = messagebox.askyesno(
            "Confirm Rename",
            f"Rename '{self.current_character}' to '{new_name}'?\n\nThis will update all references across the database."
        )

        if not confirm:
            return

        try:
            old_name = self.current_character

            # CRITICAL: Update name in characters table
            self.cursor.execute("""
                UPDATE characters
                SET name = ?
                WHERE name = ?
            """, (new_name, old_name))

            # Update character_name in movesets
            self.cursor.execute("""
                UPDATE movesets
                SET character_name = ?
                WHERE character_name = ?
            """, (new_name, old_name))

            # Update character_name in forms
            self.cursor.execute("""
                UPDATE forms
                SET character_name = ?
                WHERE character_name = ?
            """, (new_name, old_name))

            # Update character_name in effects
            self.cursor.execute("""
                UPDATE effects
                SET character_name = ?
                WHERE character_name = ?
            """, (new_name, old_name))

            # Update character_name in combat_state
            self.cursor.execute("""
                UPDATE combat_state
                SET character_name = ?
                WHERE character_name = ?
            """, (new_name, old_name))

            # Update owner_name in deployables
            self.cursor.execute("""
                UPDATE deployables
                SET owner_name = ?
                WHERE owner_name = ?
            """, (new_name, old_name))

            self.conn.commit()
            self.current_character = new_name
            self.main_title.configure(text=f"Editing: {new_name}")
            self.refresh_character_list()
            self.set_status(f"Renamed '{old_name}' to '{new_name}' successfully", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error renaming character: {e}", "error")
            messagebox.showerror("Error", f"Failed to rename character:\n{e}")

    def select_character(self, name):
        """Select a character and load their data"""
        self.current_character = name
        self.main_title.configure(text=f"Editing: {name}")

        # Load character data into tabs
        self.load_core_stats()
        self.load_attributes()
        self.load_moves_list()
        self.load_forms_list()
        self.load_deployables_list()

        self.set_status(f"Loaded {name}", "success")

    def load_core_stats(self):
        """Load core stats for current character"""
        if not self.current_character:
            return

        try:
            self.cursor.execute("""
                SELECT hp, max_hp, mp, max_mp, ac, current_stars, max_stars, proficiency
                FROM characters
                WHERE name = ?
            """, (self.current_character,))

            row = self.cursor.fetchone()
            if row:
                hp, max_hp, mp, max_mp, ac, current_stars, max_stars, proficiency = row

                self.core_entries["hp"].delete(0, "end")
                self.core_entries["hp"].insert(0, str(hp) if hp is not None else "0")

                self.core_entries["max_hp"].delete(0, "end")
                self.core_entries["max_hp"].insert(0, str(max_hp) if max_hp is not None else "0")

                self.core_entries["mp"].delete(0, "end")
                self.core_entries["mp"].insert(0, str(mp) if mp is not None else "0")

                self.core_entries["max_mp"].delete(0, "end")
                self.core_entries["max_mp"].insert(0, str(max_mp) if max_mp is not None else "0")

                self.core_entries["ac"].delete(0, "end")
                self.core_entries["ac"].insert(0, str(ac) if ac is not None else "1")

                self.core_entries["current_stars"].delete(0, "end")
                self.core_entries["current_stars"].insert(0, str(current_stars) if current_stars is not None else "5")

                self.core_entries["max_stars"].delete(0, "end")
                self.core_entries["max_stars"].insert(0, str(max_stars) if max_stars is not None else "5")

                self.core_entries["proficiency"].delete(0, "end")
                self.core_entries["proficiency"].insert(0, str(proficiency) if proficiency is not None else "0")

        except Exception as e:
            self.set_status(f"Error loading core stats: {e}", "error")

    def load_attributes(self):
        """Load attributes (JSON) for current character"""
        if not self.current_character:
            return

        try:
            self.cursor.execute("SELECT base_stats FROM characters WHERE name = ?", (self.current_character,))
            row = self.cursor.fetchone()

            if row and row[0]:
                base_stats = json.loads(row[0])

                for attr in ["str", "dex", "con", "int", "wis", "cha"]:
                    self.attr_entries[attr].delete(0, "end")
                    self.attr_entries[attr].insert(0, str(base_stats.get(attr, 0)))
            else:
                # Default to 0
                for attr in ["str", "dex", "con", "int", "wis", "cha"]:
                    self.attr_entries[attr].delete(0, "end")
                    self.attr_entries[attr].insert(0, "0")

        except Exception as e:
            self.set_status(f"Error loading attributes: {e}", "error")

    def load_moves_list(self):
        """Load moves list for current character (with form names)"""
        if not self.current_character:
            return

        try:
            self.cursor.execute("""
                SELECT form_name, move_name FROM movesets
                WHERE character_name = ?
                ORDER BY form_name, move_name
            """, (self.current_character,))

            moves = self.cursor.fetchall()

            if moves:
                # Format as [{form_name}] {move_name}
                move_options = [f"[{form}] {move}" for form, move in moves]
                self.move_selector.configure(values=move_options)
                self.move_selector.set(move_options[0])
                # Parse and load first move
                form, move = moves[0]
                self.load_move_data(move_options[0])
            else:
                self.move_selector.configure(values=["No moves available"])
                self.move_selector.set("No moves available")
                # Clear move entries
                for entry in self.move_entries.values():
                    entry.delete(0, "end")

        except Exception as e:
            self.set_status(f"Error loading moves: {e}", "error")

    def load_move_data(self, formatted_name):
        """Load data for selected move (formatted as [{form}] {move})"""
        if not self.current_character or formatted_name == "No moves available":
            return

        try:
            # Parse formatted name "[{form}] {move}"
            if "]" in formatted_name:
                form_part, move_name = formatted_name.split("] ", 1)
                form_name = form_part[1:]  # Remove leading "["
            else:
                form_name = "base"
                move_name = formatted_name

            self.current_move = move_name
            self.current_move_form = form_name

            self.cursor.execute("""
                SELECT damage, hits, mp_cost, hp_cost, star_cost, stat, bonus_on_hit, save_effect, description, uses, max_uses, duration, cooldown, self_effect, target_effect
                FROM movesets
                WHERE character_name = ? AND move_name = ? AND form_name = ?
            """, (self.current_character, move_name, form_name))

            row = self.cursor.fetchone()
            if row:
                damage, hits, mp_cost, hp_cost, star_cost, stat, bonus_on_hit, save_effect, description, uses, max_uses, duration, cooldown, self_effect, target_effect = row

                # Set form name
                self.move_entries["form_name"].delete(0, "end")
                self.move_entries["form_name"].insert(0, form_name)

                self.move_entries["damage"].delete(0, "end")
                self.move_entries["damage"].insert(0, str(damage) if damage is not None else "0")

                self.move_entries["hits"].delete(0, "end")
                self.move_entries["hits"].insert(0, str(hits) if hits is not None else "1")

                self.move_entries["mp_cost"].delete(0, "end")
                self.move_entries["mp_cost"].insert(0, str(mp_cost) if mp_cost is not None else "0")

                self.move_entries["hp_cost"].delete(0, "end")
                self.move_entries["hp_cost"].insert(0, str(hp_cost) if hp_cost is not None else "0")

                self.move_entries["star_cost"].delete(0, "end")
                self.move_entries["star_cost"].insert(0, str(star_cost) if star_cost is not None else "0")

                self.move_entries["stat"].delete(0, "end")
                self.move_entries["stat"].insert(0, str(stat) if stat else "")

                self.move_entries["bonus_on_hit"].delete(0, "end")
                self.move_entries["bonus_on_hit"].insert(0, str(bonus_on_hit) if bonus_on_hit else "")

                self.move_entries["save_effect"].delete(0, "end")
                self.move_entries["save_effect"].insert(0, str(save_effect) if save_effect else "")

                self.move_entries["self_effect"].delete(0, "end")
                self.move_entries["self_effect"].insert(0, str(self_effect) if self_effect else "")

                self.move_entries["target_effect"].delete(0, "end")
                self.move_entries["target_effect"].insert(0, str(target_effect) if target_effect else "")

                self.move_entries["uses"].delete(0, "end")
                self.move_entries["uses"].insert(0, str(uses) if uses is not None else "0")

                self.move_entries["max_uses"].delete(0, "end")
                self.move_entries["max_uses"].insert(0, str(max_uses) if max_uses is not None else "0")

                self.move_entries["duration"].delete(0, "end")
                self.move_entries["duration"].insert(0, str(duration) if duration is not None else "0")

                self.move_entries["cooldown"].delete(0, "end")
                self.move_entries["cooldown"].insert(0, str(cooldown) if cooldown is not None else "0")

                self.move_description.delete("1.0", "end")
                self.move_description.insert("1.0", description if description else "")

        except Exception as e:
            self.set_status(f"Error loading move data: {e}", "error")

    def add_move(self):
        """Add a new move to the current character"""
        if not self.current_character:
            messagebox.showerror("Error", "No character selected!")
            return

        # Prompt for move name
        move_name = simpledialog.askstring("Add Move", "Enter move name:")
        if not move_name:
            return

        # Prompt for form name
        form_name = simpledialog.askstring("Add Move", "Enter form name (default: base):", initialvalue="base")
        if not form_name:
            form_name = "base"

        try:
            # Create blank move entry
            self.cursor.execute("""
                INSERT INTO movesets (character_name, form_name, move_name, category, star_cost, mp_cost, hp_cost, damage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.current_character, form_name, move_name, "utility", 0, 0, 0, 0))

            self.conn.commit()
            self.load_moves_list()
            self.set_status(f"Added move: [{form_name}] {move_name}", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error adding move: {e}", "error")
            messagebox.showerror("Error", f"Failed to add move:\n{e}")

    def bulk_delete_moves(self):
        """Open popup window for bulk move deletion with checkboxes"""
        if not self.current_character:
            messagebox.showerror("Error", "No character selected!")
            return

        try:
            # Get all moves for this character
            self.cursor.execute("""
                SELECT form_name, move_name FROM movesets
                WHERE character_name = ?
                ORDER BY form_name, move_name
            """, (self.current_character,))

            moves = self.cursor.fetchall()

            if not moves:
                messagebox.showinfo("No Moves", "This character has no moves to delete.")
                return

            # Create popup window
            popup = ctk.CTkToplevel(self)
            popup.title("Bulk Delete Moves")
            popup.geometry("500x600")
            popup.grab_set()  # Modal

            # Title
            title = ctk.CTkLabel(
                popup,
                text=f"Select moves to delete for {self.current_character}",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            title.pack(pady=20)

            # Scrollable frame for checkboxes
            scroll_frame = ctk.CTkScrollableFrame(popup, width=450, height=400)
            scroll_frame.pack(pady=10, padx=20, fill="both", expand=True)

            # Create checkboxes for each move
            checkboxes = []
            for form_name, move_name in moves:
                var = ctk.BooleanVar(value=False)
                checkbox = ctk.CTkCheckBox(
                    scroll_frame,
                    text=f"[{form_name}] {move_name}",
                    variable=var
                )
                checkbox.pack(pady=5, padx=10, anchor="w")
                checkboxes.append((form_name, move_name, var))

            # Confirm deletion button
            def confirm_bulk_delete():
                # Get selected moves
                to_delete = [(form, move) for form, move, var in checkboxes if var.get()]

                if not to_delete:
                    messagebox.showwarning("No Selection", "No moves selected for deletion.")
                    return

                # Final confirmation
                confirm = messagebox.askyesno(
                    "Confirm Bulk Delete",
                    f"Delete {len(to_delete)} move(s)?\n\nThis cannot be undone!"
                )

                if not confirm:
                    return

                try:
                    # Delete each selected move
                    for form_name, move_name in to_delete:
                        self.cursor.execute("""
                            DELETE FROM movesets
                            WHERE character_name = ? AND move_name = ? AND form_name = ?
                        """, (self.current_character, move_name, form_name))

                    self.conn.commit()
                    self.load_moves_list()
                    self.set_status(f"Deleted {len(to_delete)} move(s) successfully", "success")
                    popup.destroy()

                except Exception as e:
                    self.conn.rollback()
                    self.set_status(f"Error deleting moves: {e}", "error")
                    messagebox.showerror("Error", f"Failed to delete moves:\n{e}")

            confirm_btn = ctk.CTkButton(
                popup,
                text="Confirm Deletion",
                fg_color="darkred",
                hover_color="red",
                command=confirm_bulk_delete,
                width=200,
                height=40
            )
            confirm_btn.pack(pady=20)

        except Exception as e:
            self.set_status(f"Error opening bulk delete: {e}", "error")
            messagebox.showerror("Error", f"Failed to open bulk delete:\n{e}")

    def rename_move(self):
        """Rename the currently selected move"""
        if not self.current_character or not self.current_move:
            messagebox.showerror("Error", "No move selected!")
            return

        # Prompt for new name
        new_name = simpledialog.askstring("Rename Move", f"Rename '{self.current_move}' to:", initialvalue=self.current_move)
        if not new_name or new_name == self.current_move:
            return

        try:
            # Update move_name in movesets
            self.cursor.execute("""
                UPDATE movesets
                SET move_name = ?
                WHERE character_name = ? AND move_name = ? AND form_name = ?
            """, (new_name, self.current_character, self.current_move, self.current_move_form))

            self.conn.commit()
            old_name = self.current_move
            self.current_move = new_name
            self.load_moves_list()
            self.set_status(f"Renamed move '{old_name}' to '{new_name}'", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error renaming move: {e}", "error")
            messagebox.showerror("Error", f"Failed to rename move:\n{e}")

    def add_form(self):
        """Add a new form to the current character"""
        if not self.current_character:
            messagebox.showerror("Error", "No character selected!")
            return

        # Prompt for form name
        form_name = simpledialog.askstring("Add Form", "Enter form name:")
        if not form_name:
            return

        try:
            # Create blank form entry
            self.cursor.execute("""
                INSERT INTO forms (character_name, form_name, ac, transformation_cost, duration, cancellable, stats_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.current_character, form_name, 1, 0, 0, 0, "{}"))

            self.conn.commit()
            self.load_forms_list()
            self.set_status(f"Added form: {form_name}", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error adding form: {e}", "error")
            messagebox.showerror("Error", f"Failed to add form:\n{e}")

    def delete_form(self):
        """Delete the currently selected form AND all associated moves"""
        if not self.current_character or not self.current_form:
            messagebox.showerror("Error", "No form selected!")
            return

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete form '{self.current_form}'?\n\nThis will also delete ALL moves for this form!\n\nThis cannot be undone!"
        )

        if not confirm:
            return

        try:
            # Delete form
            self.cursor.execute("""
                DELETE FROM forms
                WHERE character_name = ? AND form_name = ?
            """, (self.current_character, self.current_form))

            # Delete all moves for this form
            self.cursor.execute("""
                DELETE FROM movesets
                WHERE character_name = ? AND form_name = ?
            """, (self.current_character, self.current_form))

            self.conn.commit()
            self.current_form = None
            self.load_forms_list()
            self.load_moves_list()  # Refresh moves list too
            self.set_status(f"Deleted form and associated moves successfully", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error deleting form: {e}", "error")
            messagebox.showerror("Error", f"Failed to delete form:\n{e}")

    def rename_form(self):
        """Rename the currently selected form (updates forms AND movesets)"""
        if not self.current_character or not self.current_form:
            messagebox.showerror("Error", "No form selected!")
            return

        # Prompt for new name
        new_name = simpledialog.askstring("Rename Form", f"Rename '{self.current_form}' to:", initialvalue=self.current_form)
        if not new_name or new_name == self.current_form:
            return

        try:
            old_name = self.current_form

            # Update form_name in forms table
            self.cursor.execute("""
                UPDATE forms
                SET form_name = ?
                WHERE character_name = ? AND form_name = ?
            """, (new_name, self.current_character, old_name))

            # CRITICAL: Update form_name in movesets table for all moves using this form
            self.cursor.execute("""
                UPDATE movesets
                SET form_name = ?
                WHERE character_name = ? AND form_name = ?
            """, (new_name, self.current_character, old_name))

            self.conn.commit()
            self.current_form = new_name
            self.load_forms_list()
            self.load_moves_list()  # Refresh moves list to show updated form names
            self.set_status(f"Renamed form '{old_name}' to '{new_name}'", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"Error renaming form: {e}", "error")
            messagebox.showerror("Error", f"Failed to rename form:\n{e}")

    def load_forms_list(self):
        """Load forms list for current character"""
        if not self.current_character:
            return

        try:
            self.cursor.execute("""
                SELECT form_name FROM forms
                WHERE character_name = ?
                ORDER BY form_name
            """, (self.current_character,))

            forms = self.cursor.fetchall()

            if forms:
                form_names = [f[0] for f in forms]
                self.form_selector.configure(values=form_names)
                self.form_selector.set(form_names[0])
                self.load_form_data(form_names[0])
            else:
                self.form_selector.configure(values=["No forms available"])
                self.form_selector.set("No forms available")
                # Clear form entries
                for entry in self.form_entries.values():
                    entry.delete(0, "end")
                self.form_stats_json.delete("1.0", "end")

        except Exception as e:
            self.set_status(f"Error loading forms: {e}", "error")

    def load_form_data(self, form_name):
        """Load data for selected form"""
        if not self.current_character or form_name == "No forms available":
            return

        self.current_form = form_name

        try:
            self.cursor.execute("""
                SELECT ac, transformation_cost, duration, cancellable, dot_damage, dot_type, stats_json
                FROM forms
                WHERE character_name = ? AND form_name = ?
            """, (self.current_character, form_name))

            row = self.cursor.fetchone()
            if row:
                ac, transformation_cost, duration, cancellable, dot_damage, dot_type, stats_json = row

                self.form_entries["ac"].delete(0, "end")
                self.form_entries["ac"].insert(0, str(ac) if ac is not None else "")

                self.form_entries["transformation_cost"].delete(0, "end")
                self.form_entries["transformation_cost"].insert(0, str(transformation_cost) if transformation_cost is not None else "0")

                self.form_entries["duration"].delete(0, "end")
                self.form_entries["duration"].insert(0, str(duration) if duration is not None else "0")

                self.form_entries["cancellable"].delete(0, "end")
                self.form_entries["cancellable"].insert(0, str(cancellable) if cancellable is not None else "0")

                self.form_entries["dot_damage"].delete(0, "end")
                self.form_entries["dot_damage"].insert(0, str(dot_damage) if dot_damage is not None else "0")

                self.form_entries["dot_type"].delete(0, "end")
                self.form_entries["dot_type"].insert(0, str(dot_type) if dot_type else "")

                self.form_stats_json.delete("1.0", "end")
                self.form_stats_json.insert("1.0", stats_json if stats_json else "{}")

        except Exception as e:
            self.set_status(f"Error loading form data: {e}", "error")

    def load_deployables_list(self):
        """Load deployables list for current character"""
        if not self.current_character:
            return

        try:
            self.cursor.execute("""
                SELECT deployable_name FROM deployables
                WHERE owner_name = ?
                ORDER BY deployable_name
            """, (self.current_character,))

            deployables = self.cursor.fetchall()

            if deployables:
                dep_names = [d[0] for d in deployables]
                self.deployable_selector.configure(values=dep_names)
                self.deployable_selector.set(dep_names[0])
                self.load_deployable_data(dep_names[0])
            else:
                self.deployable_selector.configure(values=["No deployables available"])
                self.deployable_selector.set("No deployables available")
                # Clear deployable entries
                for entry in self.deployable_entries.values():
                    entry.delete(0, "end")

        except Exception as e:
            self.set_status(f"Error loading deployables: {e}", "error")

    def load_deployable_data(self, deployable_name):
        """Load data for selected deployable"""
        if not self.current_character or deployable_name == "No deployables available":
            return

        self.current_deployable = deployable_name

        try:
            self.cursor.execute("""
                SELECT hp, max_hp, ac, available_until_round, stars, max_stars
                FROM deployables
                WHERE owner_name = ? AND deployable_name = ?
            """, (self.current_character, deployable_name))

            row = self.cursor.fetchone()
            if row:
                hp, max_hp, ac, duration, stars, max_stars = row

                self.deployable_entries["hp"].delete(0, "end")
                self.deployable_entries["hp"].insert(0, str(hp) if hp is not None else "0")

                self.deployable_entries["max_hp"].delete(0, "end")
                self.deployable_entries["max_hp"].insert(0, str(max_hp) if max_hp is not None else "0")

                self.deployable_entries["ac"].delete(0, "end")
                self.deployable_entries["ac"].insert(0, str(ac) if ac is not None else "1")

                self.deployable_entries["duration"].delete(0, "end")
                self.deployable_entries["duration"].insert(0, str(duration) if duration is not None else "0")

                self.deployable_entries["stars"].delete(0, "end")
                self.deployable_entries["stars"].insert(0, str(stars) if stars is not None else "0")

                self.deployable_entries["max_stars"].delete(0, "end")
                self.deployable_entries["max_stars"].insert(0, str(max_stars) if max_stars is not None else "0")

        except Exception as e:
            self.set_status(f"Error loading deployable data: {e}", "error")

    def save_changes(self):
        """Save all changes to database"""
        if not self.current_character:
            self.set_status("No character selected!", "error")
            return

        try:
            # Save core stats (using safe_int)
            self.cursor.execute("""
                UPDATE characters
                SET hp = ?, max_hp = ?, mp = ?, max_mp = ?, ac = ?,
                    current_stars = ?, max_stars = ?, proficiency = ?
                WHERE name = ?
            """, (
                self.safe_int(self.core_entries["hp"].get()),
                self.safe_int(self.core_entries["max_hp"].get()),
                self.safe_int(self.core_entries["mp"].get()),
                self.safe_int(self.core_entries["max_mp"].get()),
                self.safe_int(self.core_entries["ac"].get(), 1),
                self.safe_int(self.core_entries["current_stars"].get(), 5),
                self.safe_int(self.core_entries["max_stars"].get(), 5),
                self.safe_int(self.core_entries["proficiency"].get()),
                self.current_character
            ))

            # Save attributes (JSON) - CRITICAL: Only update base_stats, NOT stats_json!
            base_stats = {
                "str": self.safe_int(self.attr_entries["str"].get()),
                "dex": self.safe_int(self.attr_entries["dex"].get()),
                "con": self.safe_int(self.attr_entries["con"].get()),
                "int": self.safe_int(self.attr_entries["int"].get()),
                "wis": self.safe_int(self.attr_entries["wis"].get()),
                "cha": self.safe_int(self.attr_entries["cha"].get())
            }
            base_stats_json = json.dumps(base_stats)

            # CRITICAL FIX: Only update base_stats, NOT stats_json (to preserve combat buffs)
            self.cursor.execute("""
                UPDATE characters
                SET base_stats = ?
                WHERE name = ?
            """, (base_stats_json, self.current_character))

            # Save move data (if a move is selected)
            if self.current_move and self.current_move != "No moves available":
                # Get new form/move names from fields
                new_form = self.move_entries["form_name"].get() or "base"
                new_move = self.current_move  # Keep same move name

                description_text = self.move_description.get("1.0", "end-1c").strip()

                self.cursor.execute("""
                    UPDATE movesets
                    SET damage = ?, hits = ?, mp_cost = ?, hp_cost = ?,
                        star_cost = ?, stat = ?, bonus_on_hit = ?, save_effect = ?,
                        self_effect = ?, target_effect = ?,
                        description = ?, uses = ?, max_uses = ?, duration = ?, cooldown = ?, form_name = ?
                    WHERE character_name = ? AND move_name = ? AND form_name = ?
                """, (
                    self.safe_int(self.move_entries["damage"].get()),
                    self.safe_int(self.move_entries["hits"].get(), 1),
                    self.safe_int(self.move_entries["mp_cost"].get()),
                    self.safe_int(self.move_entries["hp_cost"].get()),
                    self.safe_int(self.move_entries["star_cost"].get()),
                    self.move_entries["stat"].get() if self.move_entries["stat"].get() else None,
                    self.move_entries["bonus_on_hit"].get() if self.move_entries["bonus_on_hit"].get() else None,
                    self.move_entries["save_effect"].get() if self.move_entries["save_effect"].get() else None,
                    self.move_entries["self_effect"].get() if self.move_entries["self_effect"].get() else None,
                    self.move_entries["target_effect"].get() if self.move_entries["target_effect"].get() else None,
                    description_text if description_text else None,
                    self.safe_int(self.move_entries["uses"].get()),
                    self.safe_int(self.move_entries["max_uses"].get()),
                    self.safe_int(self.move_entries["duration"].get()),
                    self.safe_int(self.move_entries["cooldown"].get()),
                    new_form,
                    self.current_character,
                    self.current_move,
                    self.current_move_form  # Use OLD form in WHERE clause
                ))

                # Update current form if changed
                self.current_move_form = new_form

            # Save form data (if a form is selected)
            if self.current_form and self.current_form != "No forms available":
                try:
                    # Validate stats_json
                    stats_json_text = self.form_stats_json.get("1.0", "end-1c")
                    if stats_json_text.strip():
                        json.loads(stats_json_text)  # Validate JSON
                    else:
                        stats_json_text = "{}"

                    self.cursor.execute("""
                        UPDATE forms
                        SET ac = ?, transformation_cost = ?, duration = ?,
                            cancellable = ?, dot_damage = ?, dot_type = ?, stats_json = ?
                        WHERE character_name = ? AND form_name = ?
                    """, (
                        self.safe_int(self.form_entries["ac"].get()) if self.form_entries["ac"].get() else None,
                        self.safe_int(self.form_entries["transformation_cost"].get()),
                        self.safe_int(self.form_entries["duration"].get()),
                        self.safe_int(self.form_entries["cancellable"].get()),
                        self.safe_int(self.form_entries["dot_damage"].get()),
                        self.form_entries["dot_type"].get() if self.form_entries["dot_type"].get() else None,
                        stats_json_text,
                        self.current_character,
                        self.current_form
                    ))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in stats_json: {e}")

            # Save deployable data (if a deployable is selected)
            if self.current_deployable and self.current_deployable != "No deployables available":
                self.cursor.execute("""
                    UPDATE deployables
                    SET hp = ?, max_hp = ?, ac = ?, available_until_round = ?,
                        stars = ?, max_stars = ?
                    WHERE owner_name = ? AND deployable_name = ?
                """, (
                    self.safe_int(self.deployable_entries["hp"].get()),
                    self.safe_int(self.deployable_entries["max_hp"].get()),
                    self.safe_int(self.deployable_entries["ac"].get(), 1),
                    self.safe_int(self.deployable_entries["duration"].get()),
                    self.safe_int(self.deployable_entries["stars"].get()),
                    self.safe_int(self.deployable_entries["max_stars"].get()),
                    self.current_character,
                    self.current_deployable
                ))

            # Commit all changes
            self.conn.commit()

            self.set_status(f"✅ Successfully saved {self.current_character}!", "success")

        except Exception as e:
            self.conn.rollback()
            self.set_status(f"❌ Error saving: {e}", "error")
            messagebox.showerror("Save Error", f"Failed to save changes:\n{e}")

    def set_status(self, message, status_type="info"):
        """Set status label with colored text"""
        colors = {
            "success": "green",
            "error": "red",
            "info": "gray"
        }
        self.status_label.configure(text=message, text_color=colors.get(status_type, "gray"))

    def on_closing(self):
        """Handle window closing"""
        if self.conn:
            self.conn.close()
        self.quit()


if __name__ == "__main__":
    app = RonanDashboard()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
