The backend uses decimal feet with its origin at the north-west floor corner.
This adapter converts every length to meters and subtracts half the room width
and length from x and z. The existing three.js scene therefore remains centered
on the floor origin. Y and right-handed rotation about +Y are unchanged.
