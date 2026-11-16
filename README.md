# Scouting Liga VIPS · Villalba Gilmar

Web privada de scouting de la Liga VIPS Masculina (FBM, Grupo Impar) para el cuerpo técnico de Villalba Gilmar: clasificación con estadísticas avanzadas, ficha de cada equipo y jugador, comparativa Villalba vs rival, calendario e informes PDF descargables.

## Cómo está hecha

```
public/index.html        La web (una sola página). No contiene datos.
api/login.js             Comprueba usuario y contraseña y guarda una cookie de sesión firmada.
api/data.js              Entrega los datos de la liga solo si hay sesión iniciada.
api/logout.js            Cierra la sesión.
data/liga.json           Datos de la liga (los genera el script). No se publica como archivo.
data/calendario.csv      Las 22 jornadas con la fecha real de cada partido.
excels/                  Los Excel de cada partido descargados de la app Afición FBM.
scripts/actualizar_datos.py   Convierte los Excel en data/liga.json.
```

Los datos solo salen del servidor después de iniciar sesión, así que aunque alguien abra la web no ve nada sin la contraseña.

## Subirla a Vercel (la primera vez)

1. Crea un repositorio **privado** en GitHub y sube esta carpeta tal cual.
2. Entra en vercel.com, pulsa **Add New → Project** e importa ese repositorio.
3. En la configuración del proyecto deja **Framework Preset: Other**. No hace falta tocar nada más: `vercel.json` ya indica que la web está en `public/`.
4. En **Settings → Environment Variables** añade:
   - `APP_USER` = `villalba`
   - `APP_PASS` = `123456` (o la contraseña que queráis)
   - `APP_SECRET` = una frase larga cualquiera (sirve para firmar la sesión; cámbiala y se cierran todas las sesiones)
5. Pulsa **Deploy**. Si cambias las variables después, vuelve a desplegar para que se apliquen.

Si no pones las variables, funciona igual con `villalba` / `123456`, pero es mejor ponerlas.

## Actualizar los datos después de cada jornada

1. Descarga en la app Afición FBM el Excel de cada partido nuevo y mételo en `excels/` (el nombre da igual; los repetidos se ignoran solos).
2. Si la FBM ha cambiado la fecha de algún partido, corrígela en `data/calendario.csv`.
3. Ejecuta, desde la carpeta del repositorio:
   ```
   pip install -r scripts/requirements.txt
   python scripts/actualizar_datos.py
   ```
   El script dice cuántos partidos hay, hasta qué fecha llegan los datos y qué partidos con fecha ya pasada no tienen Excel (aplazados o archivos que faltan).
4. Sube los cambios a GitHub (`git add . && git commit -m "Jornada X" && git push`). Vercel vuelve a publicar la web solo.

## Probarla en tu ordenador (opcional)

Con Node instalado: `npm i -g vercel` y luego `vercel dev` dentro de la carpeta. Abre http://localhost:3000.

## Notas

- Las claves de cada equipo y jugador ("Cómo meterles mano", "Lo que hay que respetar", peligrosidad) se calculan solas comparando con la media de la liga, así que se actualizan con cada jornada.
- Algunos jugadores salen como "X NOMBRE" en los Excel: cuentan para los totales del equipo pero no aparecen en las tablas de jugadores.
- Las estadísticas avanzadas siguen las fórmulas habituales: posesiones = tiros de campo − rebotes ofensivos + pérdidas + 0,44 × tiros libres; TS% = puntos / (2 × (tiros de campo + 0,44 × libres)); USG% = jugadas que acaba un jugador sobre las del equipo mientras está en pista.
# villalba
