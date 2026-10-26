// Final chorus: all three bands stacked, every point in its lamp's colour from the data (td
// orange, rho blue, p-1 stage 1 deep green, stage 2 light green), dark points and the spine
// grey. The lit points ride the choir swell; "the tower's lit" (peak) is their brightest
// moment in the film. The dark points and the spine never brighten: the wall stays grey.
uniform float peak;

void main() {
    float lamp = attr.x;
    vec3 w = world(rah);
    if (lamp > 4.5) { place(w, 0.85); v_col = DARK; v_a = 0.6; return; }
    if (lamp > 3.5) { place(w, 1.0); v_col = DARK * 0.8; v_a = 1.0; return; }
    vec3 lc = lamp < 0.5 ? TD * 1.5 : lamp < 1.5 ? RHO * 1.6 : lamp < 2.5 ? PM1 * 2.0 : PM2 * 1.5;
    v_col = lc * (0.85 + 0.45 * swell + 0.9 * peak);
    v_a = 1.0 + 0.3 * kick;
    place(w, 1.0 + 0.25 * peak);
}
