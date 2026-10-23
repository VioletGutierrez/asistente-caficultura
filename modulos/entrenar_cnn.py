# ============================================================
# modulos/entrenar_cnn.py
# Entrenamiento MobileNetV3 con Transfer Learning
# Referencia: IA.docx §4.4
# Uso:
#   python -m modulos.entrenar_cnn --dataset ruta/a/dataset
# ============================================================
import os
import argparse

try:
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNetV3Small
    from tensorflow.keras.layers import (
        GlobalAveragePooling2D, Dense, Dropout,
    )
    from tensorflow.keras.models import Model
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    TF_OK = True
except ImportError:
    TF_OK = False


def construir_modelo(num_clases, img_size=224):
    base = MobileNetV3Small(
        input_shape=(img_size, img_size, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False
    x = base.output
    x = GlobalAveragePooling2D()(x)
    x = Dropout(0.3)(x)
    x = Dense(128, activation="relu")(x)
    salida = Dense(num_clases, activation="softmax")(x)
    modelo = Model(inputs=base.input, outputs=salida)
    modelo.compile(
        optimizer=Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return modelo


def entrenar(dataset_dir, epochs=15, batch_size=16, img_size=224,
             salida="modelos/cnn_cafe.h5"):
    if not TF_OK:
        print("ERROR: TensorFlow no esta instalado.")
        print("  pip install tensorflow")
        return
    if not os.path.isdir(dataset_dir):
        print(f"ERROR: no existe el directorio {dataset_dir}")
        return

    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)

    datagen = ImageDataGenerator(
        rescale=1.0 / 255,
        rotation_range=20,
        width_shift_range=0.1,
        height_shift_range=0.1,
        zoom_range=0.1,
        horizontal_flip=True,
        validation_split=0.2,
    )
    train_gen = datagen.flow_from_directory(
        dataset_dir, target_size=(img_size, img_size),
        batch_size=batch_size, class_mode="categorical",
        subset="training",
    )
    val_gen = datagen.flow_from_directory(
        dataset_dir, target_size=(img_size, img_size),
        batch_size=batch_size, class_mode="categorical",
        subset="validation",
    )

    print(f"Clases: {train_gen.class_indices}")
    print(f"Muestras train: {train_gen.samples} | val: {val_gen.samples}")

    modelo = construir_modelo(train_gen.num_classes, img_size)

    callbacks = [
        EarlyStopping(patience=3, restore_best_weights=True, verbose=1),
        ModelCheckpoint(salida, save_best_only=True, verbose=1),
    ]
    historial = modelo.fit(
        train_gen, validation_data=val_gen,
        epochs=epochs, callbacks=callbacks,
    )

    acc = max(historial.history.get("val_accuracy", [0]))
    print(f"Mejor val_accuracy: {acc*100:.2f}%")
    print(f"Modelo guardado en: {salida}")
    print("Para usarlo, verifique que vision_cnn.py cargue ese archivo.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True,
                   help="Directorio con subcarpetas por clase")
    p.add_argument("--epochs",  type=int, default=15)
    p.add_argument("--batch",   type=int, default=16)
    p.add_argument("--img",     type=int, default=224)
    p.add_argument("--salida",  default="modelos/cnn_cafe.h5")
    a = p.parse_args()
    entrenar(a.dataset, a.epochs, a.batch, a.img, a.salida)