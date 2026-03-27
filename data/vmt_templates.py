"""VMT (Valve Material Type) templates for Source Engine materials."""

# Opaque material with phong shading and half-lambert for toon-ish look
VMT_OPAQUE = '''"VertexLitGeneric"
{{
    "$basetexture"    "{cdmaterials}/{texture_name}"
{bumpmap_line}{selfillum_lines}    "$model"          "1"
    "$phong"          "1"
    "$phongboost"     "1.5"
    "$phongexponent"  "25"
    "$halflambert"    "1"
}}
'''

# Alpha-tested material (for hair, accessories with cutout transparency)
VMT_ALPHATEST = '''"VertexLitGeneric"
{{
    "$basetexture"    "{cdmaterials}/{texture_name}"
{bumpmap_line}{selfillum_lines}    "$model"          "1"
    "$phong"          "1"
    "$phongboost"     "1.5"
    "$phongexponent"  "25"
    "$halflambert"    "1"
    "$alphatest"      "1"
    "$alphatestreference" "0.5"
    "$allowalphatocoverage" "1"
}}
'''

# Translucent material (semi-transparent)
VMT_TRANSLUCENT = '''"VertexLitGeneric"
{{
    "$basetexture"    "{cdmaterials}/{texture_name}"
{bumpmap_line}{selfillum_lines}    "$model"          "1"
    "$phong"          "1"
    "$phongboost"     "1.5"
    "$phongexponent"  "25"
    "$halflambert"    "1"
    "$translucent"    "1"
}}
'''


def generate_vmt(texture_name: str, cdmaterials: str,
                 alpha_mode: str = "OPAQUE",
                 has_normal: bool = False,
                 normal_name: str = "",
                 has_emission: bool = False,
                 emission_name: str = "") -> str:
    """Generate a VMT file content string.

    Args:
        texture_name: Base texture name (without extension)
        cdmaterials: Material path relative to materials/ folder
        alpha_mode: "OPAQUE", "MASK", or "BLEND"
        has_normal: Whether a normal map exists
        normal_name: Normal map texture name
        has_emission: Whether an emission texture exists
        emission_name: Emission texture name
    """
    bumpmap_line = ""
    if has_normal and normal_name:
        bumpmap_line = f'    "$bumpmap"        "{cdmaterials}/{normal_name}"\n'

    selfillum_lines = ""
    if has_emission and emission_name:
        selfillum_lines = (
            f'    "$selfillum"     "1"\n'
            f'    "$selfillummask" "{cdmaterials}/{emission_name}"\n'
        )

    if alpha_mode == "MASK":
        template = VMT_ALPHATEST
    elif alpha_mode == "BLEND":
        template = VMT_TRANSLUCENT
    else:
        template = VMT_OPAQUE

    return template.format(
        texture_name=texture_name,
        cdmaterials=cdmaterials,
        bumpmap_line=bumpmap_line,
        selfillum_lines=selfillum_lines,
    )
