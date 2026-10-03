#!/usr/bin/env python3
"""
HEPA AIR PURIFIER  -  2 x 120 mm OR 140 mm PWM fans, cylindrical filter, STEP generator
=======================================================================================
Filter : Generic pleated cylinder. Script prompts for OD, ID, and Height.
Fans   : 2 x 120 or 140 mm, 25 mm thick, PWM  (script asks which)
Room   : < 100 sq ft, 24/7 duty  ->  quiet, low-RPM, high-efficiency layout
Printer: every part fits a 220 x 220 mm bed (square 179 mm housing, see BED_XY)

Run:      python hepa_purifier.py              (asks for filter dims & fan size)
          python hepa_purifier.py --fan 120    (skips fan prompt)
Needs:    pip install cadquery
Outputs:  hepa_purifier_out/hepa_purifier_<N>mm_assembly.step
          hepa_purifier_out/parts_<N>mm/*.step

-------------------------------------------------------------------------------
AIRFLOW ARCHITECTURE (bottom -> top)
-------------------------------------------------------------------------------
  room air -> slotted intake cage -> plenum -> pleated media (outside-in)
  -> filter bore -> 12 deg conical diffuser -> FAN 1 -> swirl straightener
  -> FAN 2 -> finger-safe exhaust grille -> room (vertical discharge)

WHY THIS LAYOUT
  1. PULL-THROUGH (fans on the clean side): even loading of the pleats, dust-free
     fan blades for 24/7 duty, and the media/bore muffles fan inlet noise.
  2. SERIES (push-pull) STACK, NOT PARALLEL: a pleated HEPA is a high-resistance
     load, so the fans live on the steep, high-pressure part of their curves.
  3. SWIRL STRAIGHTENER BETWEEN THE FANS (16 mm, 13 vanes): recovers fan 1's
     rotation as pressure and keeps fan 2 from running in pre-swirl.
  4. DIFFUSER (12 deg half-angle): widens the filter bore to the fan aperture.
     Split in half for easy printing, with a tracking tongue & groove for gluing.
  5. SQUARE HOUSING (179 x 179 mm): a round sleeve around square 140 mm fans
     would need to be >= 200 mm wide. Square fan cells keep everything 179 mm.
  6. SEALING: solid base closes the bore bottom; knife-edge ribs at the mean radius
     of the filter end-caps seal top and bottom. 

-------------------------------------------------------------------------------
BUILD NOTES
-------------------------------------------------------------------------------
  * Four M4 threaded rods in the corner columns clamp the entire stack. M4 nuts
    sit in hex pockets in the base and cap; use silicone washers to isolate vibration.
  * Fans drop into square pockets in the fan cells (0.4 mm clearance per side).
  * Diffuser bottom, diffuser top, and top cap are exported upside-down 
    (flat face on the bed, no supports needed). 
  * Add CA glue to the tracking groove when assembling the two diffuser halves.
"""

import argparse
import math
import os
import cadquery as cq

# =============================================================================
# 1. PARAMETERS  (all mm)
# =============================================================================
IN = 25.4

# --- Filter (generic cylindrical pleated HEPA default sizes) ---
DEFAULT_FILTER_OD = 5.7 * IN  # 144.78
DEFAULT_FILTER_ID = 3.7 * IN  # 93.98
DEFAULT_FILTER_H  = 4.8 * IN  # 121.92
BORE_CLEARANCE = 0.8          # radial clearance: filter bore <-> base centring nose

# --- Fan specs (envelope sizes; measure your fan if it differs) ---
FAN_SPECS = {
    120: dict(size=120.0, hole_pitch=105.0, hole_d=4.3, bore=114.0, hub=38.0, corner_r=5.0),
    140: dict(size=140.0, hole_pitch=124.5, hole_d=4.3, bore=132.0, hub=42.0, corner_r=6.0),
}
FAN_THICK = 25.0
FAN_GAP = 16.0                # series gap = swirl-straightener length
FAN_POCKET_CLEAR = 0.4        # per-side clearance in the fan pocket

# --- Square housing ---
INTAKE_GAP = 14.0             # filter OD -> inside of cage wall, per side
WALL = 3.0
BASE_T = 8.0
CAP_T = 7.0
RIB_H = 2.0
RIB_W = 3.0
NOSE_H = 40.0                 # base centring nose (also removes the dead corner)
ROD_INSET = 5.0               # tie-rod centre inset from the cage's inner wall
BOSS_R = 7.0                  # corner column radius (cage)

# --- Intake cage slots ---
SLOT_W = 7.0
SLOT_PITCH = 11.0

# --- Diffuser / straightener ---
DIFFUSER_HALF_ANGLE = 12.0    # degrees
VANE_N = 13
VANE_T = 1.2

# --- Exhaust grille (finger-safe: openings <= ~10 mm) ---
GRILLE_T = 4.0
GRILLE_RING_W = 1.6
GRILLE_GAP = 8.0
SPOKE_W = 1.6
EXIT_CHAMFER = 3.0

# --- Cable window through the fan cells ---
CABLE_W = 16.0
CABLE_H = 10.0

# --- Tie rods / nuts ---
ROD_D = 4.0
ROD_HOLE_D = 4.4
NUT_AF = 7.0                  # M4 nut across flats
NUT_T = 3.2

# --- Output / checks ---
BED_XY = 220.0                # your printer bed
OUT_DIR = "hepa_purifier_out"
ROOM_FT3 = 100 * 8            # 100 sq ft x 8 ft ceiling

# Export upside down so their flat mating faces lay perfectly on the print bed
PRINT_FLIP = {"diffuser_bottom", "diffuser_top", "top_cap"}


# =============================================================================
# 2. FAN-DEPENDENT / DERIVED GEOMETRY
# =============================================================================
class Cfg:
    def __init__(self, fan_mm, filter_od=DEFAULT_FILTER_OD, filter_id=DEFAULT_FILTER_ID, filter_h=DEFAULT_FILTER_H):
        s = FAN_SPECS[fan_mm]
        self.fan_mm = fan_mm
        self.fan = s["size"]
        self.fan_hole_pitch = s["hole_pitch"]
        self.fan_hole_d = s["hole_d"]
        self.r_bore = s["bore"] / 2
        self.r_hub = s["hub"] / 2
        self.fan_corner_r = s["corner_r"]
        self.grille_hub_r = self.r_hub - 1.0

        # Dynamic filter settings
        self.filter_od = filter_od
        self.filter_id = filter_id
        self.filter_h = filter_h

        # filter radii
        self.r_f_in = self.filter_id / 2
        self.r_f_out = self.filter_od / 2
        self.r_seal = (self.r_f_in + self.r_f_out) / 2

        # square housing; rods sit concentric with the outer corner radius
        self.s_in = float(math.ceil(self.filter_od + 2 * INTAKE_GAP))
        self.s_out = self.s_in + 2 * WALL
        self.corner_r = WALL + ROD_INSET
        self.rc = self.s_in / 2 - ROD_INSET
        self.rod_pts = [(sx * self.rc, sy * self.rc) for sx in (-1, 1) for sy in (-1, 1)]
        self.fan_hole_pts = [(sx * self.fan_hole_pitch / 2, sy * self.fan_hole_pitch / 2)
                             for sx in (-1, 1) for sy in (-1, 1)]

        # diffuser
        self.cone_h = (self.r_bore - self.r_f_in) / math.tan(math.radians(DIFFUSER_HALF_ANGLE))

        # Z stack
        self.z_f0 = BASE_T + RIB_H
        self.z_f1 = self.z_f0 + self.filter_h
        self.z_ad0 = self.z_f1 + RIB_H
        self.z_ad1 = self.z_ad0 + self.cone_h
        self.z_fan1 = self.z_ad1
        self.z_fan1_top = self.z_fan1 + FAN_THICK
        self.z_fan2 = self.z_fan1_top + FAN_GAP
        self.z_fan2_top = self.z_fan2 + FAN_THICK
        self.z_cap0 = self.z_fan2_top
        self.z_top = self.z_cap0 + CAP_T

        # intake slots (10 mm clear of each end)
        self.slot_z0 = BASE_T + 10.0
        self.slot_z1 = self.z_ad0 - 10.0
        self.slot_l = self.slot_z1 - self.slot_z0
        half_span = self.rc - BOSS_R - 5.0 - SLOT_W / 2
        self.slot_n = int(2 * half_span // SLOT_PITCH) + 1
        self.slot_x = [(i - (self.slot_n - 1) / 2) * SLOT_PITCH for i in range(self.slot_n)]

        # sanity checks
        assert self.r_bore > self.r_f_in, "Fan aperture must be wider than the filter inner bore"
        assert self.fan / 2 + FAN_POCKET_CLEAR + 4 < self.rc - ROD_HOLE_D / 2, \
            "Fan too large for the corner rods - raise INTAKE_GAP"
        assert self.s_in - self.filter_od >= 2 * 10, "Intake plenum gap too small"
        assert self.s_out <= BED_XY - 20, f"Housing {self.s_out} mm too big for a {BED_XY} mm bed"


# =============================================================================
# 3. HELPERS
# =============================================================================
def disc(r, h, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).circle(r).extrude(h)


def ring(r_out, r_in, h, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).circle(r_out).circle(r_in).extrude(h)


def rrect(side, h, z0, r):
    """Rounded-square prism."""
    return (cq.Workplane("XY").workplane(offset=z0).rect(side, side).extrude(h)
            .edges("|Z").fillet(r))


def block(c, h, z0):
    """Full outer housing prism."""
    return rrect(c.s_out, h, z0, c.corner_r)


def revolve_rz(pts):
    """Revolve a closed (r, z) polyline 360 deg about the global Z axis."""
    return (cq.Workplane("XZ").polyline(pts).close()
            .revolve(360, (0, 0, 0), (0, 1, 0)))


def rod_holes(c, z0, h, d=ROD_HOLE_D):
    return (cq.Workplane("XY").workplane(offset=z0)
            .pushPoints(c.rod_pts).circle(d / 2).extrude(h))


def nut_pockets(c, z0, h):
    across_corners = NUT_AF / math.cos(math.radians(30)) + 0.4
    return (cq.Workplane("XY").workplane(offset=z0)
            .pushPoints(c.rod_pts).polygon(6, across_corners).extrude(h))


# =============================================================================
# 4. PARTS
# =============================================================================
def make_base(c):
    """Solid base: closes the filter bore, centres + seals the filter."""
    b = block(c, BASE_T, 0)
    b = b.union(ring(c.r_seal + RIB_W / 2, c.r_seal - RIB_W / 2, RIB_H, BASE_T))
    r_b = c.r_f_in - BORE_CLEARANCE
    nose = revolve_rz([(0, BASE_T - 1.0), (r_b, BASE_T - 1.0), (r_b, c.z_f0 + 10.0),
                       (14.0, c.z_f0 + NOSE_H), (0, c.z_f0 + NOSE_H)])
    b = b.union(nose)
    b = b.cut(rod_holes(c, -1.0, BASE_T + 2.0))
    b = b.cut(nut_pockets(c, -0.01, NUT_T + 0.4))                  # from the underside
    return b


def make_cage(c):
    """Square slotted intake sleeve with corner columns for the tie rods."""
    h = c.z_ad0 - BASE_T
    outer = rrect(c.s_out, h, BASE_T, c.corner_r)
    cavity = rrect(c.s_in, h + 2.0, BASE_T - 1.0, c.corner_r - WALL)
    bosses = (cq.Workplane("XY").workplane(offset=BASE_T - 1.0)
              .pushPoints(c.rod_pts).circle(BOSS_R).extrude(h + 2.0))
    cage = outer.cut(cavity.cut(bosses))

    zc = (c.slot_z0 + c.slot_z1) / 2
    tools = []
    for x in c.slot_x:
        t = (cq.Workplane("XZ").center(x, zc).slot2D(c.slot_l, SLOT_W, 90)
             .extrude(c.s_out, both=True)).val()
        tools += [t, t.rotate((0, 0, 0), (0, 0, 1), 90)]           # +/-Y walls, then +/-X walls
    cage = cage.cut(cq.Compound.makeCompound(tools))
    return cage.cut(rod_holes(c, BASE_T - 1.0, h + 2.0))


def make_diffuser_halves(c):
    """Solid block split in two: bore -> fan aperture, seals the filter top. 
    Includes self-aligning tracking groove/lip for gluing."""
    z_cut = c.z_ad0 + c.cone_h / 2.0
    
    # Bottom block
    bottom = block(c, c.cone_h / 2.0, c.z_ad0)
    bottom = bottom.union(ring(c.r_seal + RIB_W / 2, c.r_seal - RIB_W / 2, RIB_H, c.z_ad0 - RIB_H))
    
    # Top block
    top = block(c, c.cone_h / 2.0, z_cut)
    
    # The cone cut applies to both
    cone = revolve_rz([(0, c.z_ad0 - 1.0), (c.r_f_in, c.z_ad0 - 1.0), (c.r_f_in, c.z_ad0),
                       (c.r_bore, c.z_ad1), (c.r_bore, c.z_ad1 + 1.0), (0, c.z_ad1 + 1.0)])
    
    bottom = bottom.cut(cone)
    top = top.cut(cone)
    
    # Tie rods cut
    bottom = bottom.cut(rod_holes(c, c.z_ad0 - 1.0, (c.cone_h / 2.0) + 2.0))
    top = top.cut(rod_holes(c, z_cut - 1.0, (c.cone_h / 2.0) + 2.0))
    
    # Tracking groove & lip at Z_cut
    r_cone_cut = c.r_f_in + (c.r_bore - c.r_f_in) * 0.5
    r_track = r_cone_cut + 6.0
    
    # Ensure the track doesn't breach the outer housing wall or tie rod holes
    max_track_wall = c.s_in / 2 - 2.0
    r_track = min(r_track, max_track_wall)

    # Tongue protruding DOWN from the top block
    # Will print upwards when flipped upside down
    tongue = ring(r_track + 0.8, r_track - 0.8, 1.8, z_cut - 1.8)
    top = top.union(tongue)
    
    # Groove cutting DOWN into the bottom block
    # Prints on the bed as an empty channel when flipped upside down
    groove = ring(r_track + 1.0, r_track - 1.0, 2.1, z_cut - 2.1)
    bottom = bottom.cut(groove)
    
    return bottom, top


def make_fan_cell(c, z0):
    """Square block with a fan-shaped pocket; locates the fan exactly."""
    k = block(c, FAN_THICK, z0)
    side = c.fan + 2 * FAN_POCKET_CLEAR
    k = k.cut(rrect(side, FAN_THICK + 2.0, z0 - 1.0, c.fan_corner_r + FAN_POCKET_CLEAR))
    x0, x1 = side / 2 - 2.0, c.s_out / 2 + 2.0                       # cable window on +X
    win = (cq.Workplane("XY").box(x1 - x0, CABLE_W, CABLE_H)
           .translate(((x0 + x1) / 2, 0, z0 + FAN_THICK / 2)))
    k = k.cut(win)
    return k.cut(rod_holes(c, z0 - 1.0, FAN_THICK + 2.0))


def make_straightener(c):
    """Plate between the fans carrying the swirl-recovery vanes."""
    z0 = c.z_fan1_top
    p = block(c, FAN_GAP, z0).cut(disc(c.r_bore, FAN_GAP + 2.0, z0 - 1.0))
    p = p.union(disc(c.r_hub, FAN_GAP, z0))
    vane_len = c.r_bore - c.r_hub + 6.0
    vane_cx = (c.r_bore + c.r_hub) / 2
    for i in range(VANE_N):
        v = (cq.Workplane("XY").workplane(offset=z0).center(vane_cx, 0)
             .rect(vane_len, VANE_T).extrude(FAN_GAP)
             .rotate((0, 0, 0), (0, 0, 1), i * 360.0 / VANE_N))
        p = p.union(v)
    return p.cut(rod_holes(c, z0 - 1.0, FAN_GAP + 2.0))


def make_cap(c):
    """Top plate with a low-restriction, finger-safe ring-and-spoke exhaust guard."""
    cap = block(c, CAP_T, c.z_cap0)
    cap = cap.cut(disc(c.r_bore, CAP_T + 2.0, c.z_cap0 - 1.0))

    gz0 = c.z_top - GRILLE_T
    g = disc(c.grille_hub_r, GRILLE_T, gz0)
    r_in = c.grille_hub_r + GRILLE_GAP
    while r_in + GRILLE_RING_W <= c.r_bore - 5.0:
        g = g.union(ring(r_in + GRILLE_RING_W, r_in, GRILLE_T, gz0))
        r_in += GRILLE_GAP + GRILLE_RING_W
    for ang in (0, 45, 90, 135):
        sp = (cq.Workplane("XY").workplane(offset=gz0)
              .rect(2 * (c.r_bore + 1.0), SPOKE_W).extrude(GRILLE_T)
              .rotate((0, 0, 0), (0, 0, 1), ang))
        g = g.union(sp)
    cap = cap.union(g)

    lip = revolve_rz([(c.r_bore, c.z_top - EXIT_CHAMFER), (c.r_bore + EXIT_CHAMFER, c.z_top),
                      (c.r_bore + EXIT_CHAMFER, c.z_top + 1.0), (c.r_bore, c.z_top + 1.0)])
    cap = cap.cut(lip)
    cap = cap.cut(rod_holes(c, c.z_cap0 - 1.0, CAP_T + 2.0))
    return cap.cut(nut_pockets(c, c.z_top - NUT_T - 0.4, NUT_T + 1.0))


# --- placeholders for fit-checking (not printed) ---------------------------
def make_filter(c):
    return ring(c.r_f_out, c.r_f_in, c.filter_h, c.z_f0)


def make_fan(c, z0):
    f = (cq.Workplane("XY").rect(c.fan, c.fan).extrude(FAN_THICK)
         .edges("|Z").fillet(c.fan_corner_r))
    f = f.cut(disc(c.r_bore, FAN_THICK))
    f = f.cut(cq.Workplane("XY").pushPoints(c.fan_hole_pts)
              .circle(c.fan_hole_d / 2).extrude(FAN_THICK))
    f = f.union(disc(c.r_hub, FAN_THICK - 3.0, 3.0))                 # rotor hub
    for ang in (45, 135):                                            # motor struts, exhaust side
        s = (cq.Workplane("XY").workplane(offset=FAN_THICK - 3.0)
             .rect(2 * (c.r_bore + 1.0), 3.0).extrude(3.0)
             .rotate((0, 0, 0), (0, 0, 1), ang))
        f = f.union(s)
    return f.translate((0, 0, z0))


def make_rods(c):
    return (cq.Workplane("XY").pushPoints(c.rod_pts).circle(ROD_D / 2).extrude(c.z_top))


# =============================================================================
# 5. DESIGN REPORT
# =============================================================================
def design_report(c):
    cfm = 0.000471947                                                # m^3/s per CFM
    a_outer = math.pi * c.filter_od * c.filter_h / 1e6
    a_bore = math.pi / 4 * c.filter_id ** 2 / 1e6
    slot_a = SLOT_W * (c.slot_l - SLOT_W) + math.pi / 4 * SLOT_W ** 2
    a_slot = 4 * c.slot_n * slot_a / 1e6
    zone = 4 * c.slot_n * SLOT_PITCH * c.slot_l / 1e6
    a_fan = math.pi * (c.r_bore ** 2 - c.r_hub ** 2) / 1e6
    print("=" * 76)
    print(f" {c.fan_mm} mm fans | housing {c.s_out:.0f} x {c.s_out:.0f} mm square "
          f"({c.s_out / IN:.1f} in), {c.z_top:.0f} mm tall ({c.z_top / IN:.1f} in)")
    print(f" Filter Size: {c.filter_od / IN:.2f} in OD x {c.filter_id / IN:.2f} in ID x {c.filter_h / IN:.2f} in H")
    print(f" Diffuser {c.cone_h:.0f} mm tall, {DIFFUSER_HALF_ANGLE:.0f} deg half-angle, "
          f"area ratio {(c.r_bore / c.r_f_in) ** 2:.2f}:1")
    print(f" Intake   {(c.s_in - c.filter_od) / 2:.0f} mm gap/side, slotted zone {100 * a_slot / zone:.0f} % open")
    print(f" Tie rods 4 x M4 x {math.ceil(c.z_top / 5) * 5:.0f} mm (trim to {c.z_top:.0f} mm)")
    print("-" * 76)
    print(" CFM   ACH     media-face   cage    bore    bore q   fan-annulus")
    print("      (100sf)     m/s       m/s     m/s     Pa         m/s")
    for q_cfm in (30, 45, 60, 75):
        q = q_cfm * cfm
        vb = q / a_bore
        print(f" {q_cfm:3d}  {q_cfm * 60 / ROOM_FT3:4.1f}      {q / a_outer:5.2f}      "
              f"{q / a_slot:5.2f}   {vb:5.2f}   {0.5 * 1.2 * vb ** 2:5.1f}      {q / a_fan:5.2f}")
    print("=" * 76)


# =============================================================================
# 6. BUILD + EXPORT
# =============================================================================
def build(c):
    cells = [make_fan_cell(c, c.z_fan1), make_fan_cell(c, c.z_fan2)]
    
    diff_bottom, diff_top = make_diffuser_halves(c)

    printed = {
        "base":            make_base(c),
        "intake_cage":     make_cage(c),
        "diffuser_bottom": diff_bottom,
        "diffuser_top":    diff_top,
        "fan_cell":        cells[0],                                     # print x2
        "straightener":    make_straightener(c),
        "top_cap":         make_cap(c),
    }
    dark, metal, light, blue = (0.25, 0.25, 0.28), (0.55, 0.57, 0.60), (0.95, 0.95, 0.90), (0.20, 0.45, 0.70)
    assembly_items = {
        "base":            (printed["base"], dark),
        "intake_cage":     (printed["intake_cage"], metal),
        "filter_HEPA":     (make_filter(c), light),
        "diffuser_bottom": (printed["diffuser_bottom"], blue),
        "diffuser_top":    (printed["diffuser_top"], blue),
        "fan_cell_1":      (cells[0], metal),
        "fan_1":           (make_fan(c, c.z_fan1), (0.10, 0.10, 0.10)),
        "straightener":    (printed["straightener"], blue),
        "fan_cell_2":      (cells[1], metal),
        "fan_2":           (make_fan(c, c.z_fan2), (0.10, 0.10, 0.10)),
        "top_cap":         (printed["top_cap"], dark),
        "tie_rods":        (make_rods(c), (0.80, 0.80, 0.82)),
    }
    return printed, assembly_items


def print_ready(name, wp):
    """Orient a part for support-free printing, sit it on z=0, centre it in XY."""
    s = wp.val()
    if name in PRINT_FLIP:
        s = s.rotate((0, 0, 0), (1, 0, 0), 180)
    bb = s.BoundingBox()
    return s.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def interference(items):
    names = list(items)
    bad = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = items[names[i]][0].val().intersect(items[names[j]][0].val()).Volume()
            if v > 1.0:
                bad.append((names[i], names[j], v))
    return bad


def ask_fan_size():
    while True:
        try:
            raw = input("Which fan size do you want to use? [120 / 140] (Enter = 140): ")
        except EOFError:
            print("\nNo input available - defaulting to 140 mm.")
            return 140
        raw = raw.strip().lower().replace("mm", "").strip()
        if raw == "":
            return 140
        if raw in ("120", "140"):
            return int(raw)
        print("  Please type 120 or 140.")


def ask_filter_dims():
    print("\n--- Custom Filter Dimensions ---")
    print("Enter values in mm, or append 'in' for inches (e.g., 145 or 5.7in).")
    print("Press Enter on any prompt to keep the default generic HEPA value.")
    
    def get_val(prompt_text, default_in):
        while True:
            try:
                raw = input(f"{prompt_text} [default {default_in}in]: ").strip().lower()
            except EOFError:
                print()
                return default_in * IN
            
            if not raw:
                return default_in * IN
            
            try:
                if raw.endswith('in') or raw.endswith('"') or raw.endswith('inch'):
                    return float(raw.replace('inch', '').replace('in', '').replace('"', '').strip()) * IN
                elif raw.endswith('mm'):
                    return float(raw.replace('mm', '').strip())
                else:
                    # Assumes mm as the fallback unit unless it's suspiciously small 
                    val = float(raw)
                    return (val * IN) if val < 20.0 else val 
            except ValueError:
                print("  Invalid input. Please enter a number (e.g. 145 or 5.7in).")

    od = get_val("Outer Diameter (OD)", 5.7)
    id_ = get_val("Inner Diameter (ID)", 3.7)
    h = get_val("Height (H)", 4.8)
    
    if id_ >= od:
        print("  Warning: Inner Diameter must be smaller than Outer Diameter. Reverting to defaults.")
        return DEFAULT_FILTER_OD, DEFAULT_FILTER_ID, DEFAULT_FILTER_H

    return od, id_, h


def main():
    ap = argparse.ArgumentParser(description="HEPA purifier STEP generator")
    ap.add_argument("--fan", type=int, choices=sorted(FAN_SPECS), help="fan size in mm (skips the fan prompt)")
    ap.add_argument("--filter-od", type=float, help="Filter Outer Diameter in mm (skips the filter prompt if all 3 provided)")
    ap.add_argument("--filter-id", type=float, help="Filter Inner Diameter in mm")
    ap.add_argument("--filter-h", type=float, help="Filter Height in mm")
    ap.add_argument("--out", default=OUT_DIR, help="output folder")
    ap.add_argument("--no-check", action="store_true", help="skip the interference check")
    args = ap.parse_args()

    fan_mm = args.fan or ask_fan_size()

    # Determine filter sizes (via args, interactive prompt, or defaults)
    if args.filter_od or args.filter_id or args.filter_h:
        f_od = args.filter_od or DEFAULT_FILTER_OD
        f_id = args.filter_id or DEFAULT_FILTER_ID
        f_h  = args.filter_h or DEFAULT_FILTER_H
    else:
        f_od, f_id, f_h = ask_filter_dims()

    c = Cfg(fan_mm, filter_od=f_od, filter_id=f_id, filter_h=f_h)
    design_report(c)

    printed, items = build(c)
    os.makedirs(args.out, exist_ok=True)

    assy = cq.Assembly(name=f"HEPA_purifier_{fan_mm}mm")
    for name, (shape, col) in items.items():
        assy.add(shape, name=name, color=cq.Color(*col))
    step_path = os.path.join(args.out, f"hepa_purifier_{fan_mm}mm_assembly.step")
    
    if hasattr(assy, "export"):
        assy.export(step_path, "STEP")
    else:                                                            # older CadQuery
        assy.save(step_path, "STEP")
    print(f"Assembly STEP   -> {step_path}")

    pdir = os.path.join(args.out, f"parts_{fan_mm}mm")
    os.makedirs(pdir, exist_ok=True)
    biggest = 0.0
    for name, wp in printed.items():
        s = print_ready(name, wp)
        bb = s.BoundingBox()
        biggest = max(biggest, bb.xlen, bb.ylen)
        cq.exporters.export(s, os.path.join(pdir, f"{name}.step"))
        print(f"   {name:15s} {bb.xlen:5.0f} x {bb.ylen:5.0f} x {bb.zlen:5.0f} mm"
              + ("   (print x2)" if name == "fan_cell" else ""))
    print(f"Printable parts -> {pdir}/")
    print(f"Largest footprint {biggest:.0f} mm vs {BED_XY:.0f} mm bed: "
          + ("fits." if biggest <= BED_XY - 10 else "TOO BIG - check BED_XY / INTAKE_GAP."))

    if not args.no_check:
        bad = interference(items)
        if bad:
            print("INTERFERENCE FOUND:")
            for a, b, v in bad:
                print(f"   {a} x {b}: {v:.1f} mm^3")
        else:
            print("Interference check: no overlapping parts.")


if __name__ == "__main__":
    main()
