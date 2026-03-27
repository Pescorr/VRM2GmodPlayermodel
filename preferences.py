import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty


class VRM2GmodPreferences(AddonPreferences):
    bl_idname = __package__

    vtfcmd_path: StringProperty(
        name="VTFCmd.exe パス",
        description="VTFCmd.exe の絶対パス（PNG→VTF変換に使用）",
        subtype='FILE_PATH',
        default="",
    )

    studiomdl_path: StringProperty(
        name="studiomdl.exe パス",
        description="studiomdl.exe の絶対パス（MDLコンパイルに使用）",
        subtype='FILE_PATH',
        default="",
    )

    gmod_addons_path: StringProperty(
        name="GMod addons フォルダ",
        description="Garry's Mod の addons フォルダパス（直接出力時に使用）",
        subtype='DIR_PATH',
        default="",
    )

    default_output_path: StringProperty(
        name="デフォルト出力先",
        description="変換結果のデフォルト出力先フォルダ",
        subtype='DIR_PATH',
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="外部ツール設定", icon='PREFERENCES')
        layout.prop(self, "vtfcmd_path")
        layout.prop(self, "studiomdl_path")
        layout.separator()
        layout.label(text="出力設定", icon='EXPORT')
        layout.prop(self, "gmod_addons_path")
        layout.prop(self, "default_output_path")


def get_preferences() -> VRM2GmodPreferences:
    return bpy.context.preferences.addons[__package__].preferences


classes = (VRM2GmodPreferences,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
