"""
Test rápido del extractor de artefactos Java.
Uso: .venv\Scripts\python test_artifact.py <archivo.war|ear|jar>
"""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))

from main import _extract_artifact_inventory, _decompress_to_artifact

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_artifact.py <archivo.war|ear|jar|zip|gz>")
        print("\nEjemplo con un JAR del sistema:")
        import glob
        jars = glob.glob("C:/Program Files/Java/**/*.jar", recursive=True)[:3]
        if jars:
            print(f"  python test_artifact.py \"{jars[0]}\"")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Archivo no encontrado: {path}")
        sys.exit(1)

    filename = os.path.basename(path)
    with open(path, "rb") as f:
        file_bytes = f.read()

    print(f"\n{'='*60}")
    print(f"  Analizando: {filename} ({len(file_bytes)//1024} KB)")
    print(f"{'='*60}\n")

    # Descomprimir si es necesario
    artifact_bytes, artifact_name = _decompress_to_artifact(file_bytes, filename)
    if artifact_name != filename:
        print(f">> Descomprimido: {filename} → {artifact_name} ({len(artifact_bytes)//1024} KB)\n")

    inventory = _extract_artifact_inventory(artifact_bytes, artifact_name)
    print(inventory)
    print(f"\n{'='*60}")
    print(f"  Total inventario: {len(inventory)} caracteres")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
