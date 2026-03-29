Shader "AYE/TentacleSoftLine"
{
    Properties
    {
        _MainTex ("Soft Line Texture", 2D) = "white" {}
        _Tint ("Tint", Color) = (1, 1, 1, 1)
        _EdgeSoftness ("Edge Softness", Range(0.4, 4.0)) = 1.85
        _CoreBoost ("Core Boost", Range(0.1, 2.0)) = 0.72
        _RimBoost ("Rim Boost", Range(0.0, 1.0)) = 0.12
        _Emission ("Emission", Range(0.0, 1.5)) = 0.28
    }

    SubShader
    {
        Tags
        {
            "Queue" = "Transparent"
            "RenderType" = "Transparent"
            "IgnoreProjector" = "True"
            "PreviewType" = "Plane"
            "CanUseSpriteAtlas" = "True"
        }

        Cull Off
        Lighting Off
        ZWrite Off
        Blend One OneMinusSrcAlpha

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            float4 _MainTex_ST;
            fixed4 _Tint;
            float _EdgeSoftness;
            float _CoreBoost;
            float _RimBoost;
            float _Emission;

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                fixed4 color : COLOR;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
                fixed4 color : COLOR;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.color = v.color * _Tint;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 tex = tex2D(_MainTex, i.uv);
                float widthCoord = saturate(1.0 - abs(i.uv.y * 2.0 - 1.0));
                float edge = pow(saturate(widthCoord), max(0.25, _EdgeSoftness));
                float core = pow(saturate(widthCoord), max(0.1, _CoreBoost));
                float rim = pow(1.0 - saturate(widthCoord), 1.6) * _RimBoost;

                float alpha = saturate(edge + tex.a * 0.35) * i.color.a;
                fixed3 rgb = tex.rgb * i.color.rgb;
                rgb *= saturate(0.82 + core * (1.05 + _Emission) + rim);
                rgb *= alpha;
                return fixed4(rgb, alpha);
            }
            ENDCG
        }
    }

    Fallback "Sprites/Default"
}