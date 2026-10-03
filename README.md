# Series-Stacked HEPA Purifier (Dual 140mm)

A 3D-printed, high-efficiency room air purifier utilizing a cylindrical HEPA filter and two 140mm High Static Pressure (HSP) PC fans in a series-stacked configuration. 

If you've researched DIY air purifiers online, you've likely encountered a common claim: *"PC fans cannot push air through a HEPA filter because they don't generate enough static pressure."* 

This README breaks down the fluid dynamics and math proving why that claim is based on a misunderstanding of system impedance, and how series-stacking, swirl recovery, and acoustic tuning solve the problem.

---

## The Myth: "PC Fans Lack the Pressure for HEPA"

The skepticism online stems from comparing two mismatched static figures:
1. **The Filter's Rated Pressure Drop:** A standard pleated filter might list a pressure drop of $250 \text{ Pa}$ ($1.0 \text{ mmH}_2\text{O}$).
2. **The Fan's Rated Static Pressure:** A premium 140mm PC fan might max out at $25 \text{ Pa}$ ($2.5 \text{ mmH}_2\text{O}$).

If $25 \text{ Pa} < 250 \text{ Pa}$, the fan stalls, right? **Wrong.** 

This assumes the filter's pressure drop is a static, unchanging wall. In reality, a filter's resistance is a curve that depends entirely on airflow. The $250 \text{ Pa}$ rating is usually calculated at an HVAC system's flow rate of **300+ CFM**. We are targeting **40 to 60 CFM** for a single room.

### 1. The Math of Filter Resistance (System Impedance)
Airflow through the densely packed micro-glass fibers of a HEPA filter is strictly in the **laminar flow regime**. According to Darcy's Law for porous media, pressure drop ($\Delta P$) in laminar flow scales *linearly* with velocity (and therefore volumetric flow rate, $Q$):

$$ \Delta P = R \cdot Q $$

If a filter creates $250 \text{ Pa}$ of resistance at $300 \text{ CFM}$, we can find its resistance coefficient ($R$):

$$ R = \frac{250 \text{ Pa}}{300 \text{ CFM}} = 0.833 \text{ Pa/CFM} $$

If we only need $60 \text{ CFM}$ to achieve 4.5 Air Changes per Hour (ACH) in a 100 sq ft room, the actual pressure drop we must overcome is:

$$ \Delta P_{target} = 0.833 \cdot 60 = 50 \text{ Pa} $$

A single 140mm PC fan maxing out at $25 \text{ Pa}$ still cannot overcome this. This is where the series stack comes in.

### 2. The Math of Series Stacking
When fans are placed side-by-side (parallel), their volumetric flow ($Q$) adds together, but their pressure limit ($\Delta P$) remains the same. When fans are placed front-to-back (**series**), their volumetric flow remains the same, but their **static pressure limits add together**.

$$ \Delta P_{total} = \Delta P_1 + \Delta P_2 $$

Two $25 \text{ Pa}$ fans in series generate a maximum static pressure of **$50 \text{ Pa}$**. 

By plotting the combined fan curve (which slopes down as flow increases) against the filter's linear impedance curve (which slopes up as flow increases), the lines intersect at the **Operating Point**. Two 140mm HSP fans in series shift the pressure curve high enough to intersect the filter's impedance curve right at our $40 \text{-} 60 \text{ CFM}$ target.

---

## Aerodynamic Optimizations

Brute-forcing pressure isn't enough; the air must be managed efficiently to prevent turbulence and stalling. This design incorporates three specific aerodynamic features:

### The 12-Degree Diffuser
Air exiting the $94\text{ mm}$ inner bore of the filter must expand to hit the $132\text{ mm}$ swept area of the 140mm fans. If the transition is an abrupt flat step, flow separates, creating a low-pressure vortex that acts like a solid wall, artificially increasing system impedance. 
* This design uses a **$12^\circ$ half-angle conical diffuser**. Fluid dynamics dictates that a divergence angle under $15^\circ$ prevents boundary layer separation, allowing kinetic energy to efficiently convert back to static pressure before hitting the first fan.

### The Swirl Straightener
Axial fans impart a corkscrew rotation (swirl) to the air. If Fan 1 feeds directly into Fan 2, Fan 2's blades are hitting air that is already rotating in the same direction. This effectively reduces Fan 2's relative angle of attack to zero, rendering it useless. 
* Between the two fans is a **16mm deep, 13-vane stator**. It recovers the rotational kinetic energy of Fan 1, converting it into axial static pressure, and feeds non-rotating air into Fan 2 so it can bite the air and multiply the pressure curve properly. (13 is a prime number to prevent harmonic tonal resonance with standard 7- or 9-blade fan rotors).

### Acoustic Tuning (PWM Offset)
When two identical motors spin at the exact same RPM in a shared structural tube, they drift in and out of phase, creating a loud, pulsing harmonic hum (beating). 
* The custom ESP32 firmware drives the two fans on independent PWM channels. Fan 2 is mathematically offset to run **10% faster** than Fan 1. This prevents phase-locking and completely eliminates the beating frequency, resulting in a smooth, steady white noise.
