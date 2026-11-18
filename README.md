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
data/plantillas.csv      Dorsal, nombre, altura y puesto de cada jugador (sacado de la guía de la liga).
excels/                  Los Excel de cada partido descargados de la app Afición FBM.
scripts/actualizar_datos.py   Convierte los Excel en data/liga.json.
```

Los datos solo salen del servidor después de iniciar sesión, así que aunque alguien abra la web no ve nada sin la contraseña.

## Subirla a Vercel (la primera vez)

1. Crea un repositorio **privado** en GitHub y sube esta carpeta tal cual.
2. Entra en vercel.com, pulsa **Add New → Project** e importa ese repositorio.
3. En la configuración del proyecto deja **Framework Preset: Other**. No hace falta tocar nada más: `vercel.json` ya indica que la web está en `public/`.
4. En **Settings → Environment Variables** añade:
   - `APP_USER` = el usuario de acceso
   - `APP_PASS` = la contraseña de acceso
   - `APP_SECRET` = una frase larga cualquiera (sirve para firmar la sesión; cámbiala y se cierran todas las sesiones)
5. Pulsa **Deploy**. Si cambias las variables después, vuelve a desplegar para que se apliquen.

## Actualizar los datos después de cada jornada

1. Descarga en la app Afición FBM el Excel de cada partido nuevo y mételo en `excels/` (el nombre da igual; los repetidos se ignoran solos).
2. Si la FBM ha cambiado la fecha de algún partido, corrígela en `data/calendario.csv`.
   Si aparece un jugador nuevo, añádelo a `data/plantillas.csv` con su puesto (el script avisa de los que no encuentra; mientras tanto, la web estima su puesto por sus números).
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
- **Nivel real**: diferencia de puntos por 100 posesiones descontando el nivel de los rivales que ha tenido cada equipo y si jugó en casa o fuera. De ahí sale el **pronóstico orientativo** de cada partido; con pocas jornadas es solo una referencia.
- **Con él / sin él**: diferencia de puntos del equipo cada 40 minutos con un jugador en pista y cuando está sentado (sale del +/- de los Excel). Solo se muestra si ha jugado al menos 100 minutos y ha descansado al menos 60.
- Para decidir quién es tirador o mal tirador de libres, los porcentajes con pocos tiros se acercan a la media de la liga, para no fiarse de una racha de dos partidos. El porcentaje que se enseña es siempre el real.
# villalba
