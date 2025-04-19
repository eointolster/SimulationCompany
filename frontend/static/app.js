// SoftwareSim3d/frontend/static/app.js

// --- Ensure libs are loaded ---
if (typeof THREE === 'undefined') console.error('Three.js not loaded!');
if (typeof io === 'undefined') console.error('Socket.IO not loaded!');
if (typeof THREE.OrbitControls === 'undefined') console.error('OrbitControls not loaded!');

// --- Constants ---
const AGENT_MOVEMENT_SPEED = 5.0; // Units per second for agent movement
const BUILDING_WIDTH = 150;
const BUILDING_DEPTH = 100;
const WALL_HEIGHT = 10;
const PARTITION_HEIGHT = 2.5;
const EXTERIOR_GROUND_SIZE = 300;

// --- Zone Definitions (Using Backend Naming Convention for consistency) ---
// Coordinates are THREE.JS Coordinates (Y=Height, Z=Depth, inverted from backend Z)
const ZONE_DEFINITIONS = {
    "CEO_OFFICE":        { center: new THREE.Vector3(0,  0.06,  24), size: new THREE.Vector2(18, 12), color: 0x8899AA }, // Z inverted from backend (-24)
    "PM_DESK_ZONE":      { center: new THREE.Vector3(-30, 0.06,  10), size: new THREE.Vector2(10, 10), color: 0x8090A0 }, // Z inverted from backend (-10)
    "MKT_DESK_ZONE":     { center: new THREE.Vector3( 30, 0.06,  10), size: new THREE.Vector2(10, 10), color: 0x8090A0 }, // Z inverted from backend (-10)
    "CODER_DESK_ZONE":   { center: new THREE.Vector3( 30, 0.06, -15), size: new THREE.Vector2(10, 10), color: 0x9088AA }, // Z inverted from backend (15)
    "QA_DESK_ZONE":      { center: new THREE.Vector3( 35, 0.06, -15), size: new THREE.Vector2( 5, 10), color: 0x9088AA }, // Z inverted from backend (15)
    "SAVE_ZONE":         { center: new THREE.Vector3( 35, 0.1,   25), size: new THREE.Vector2( 5,  5), color: 0x008080, borderColor: 0x00DDDD, label: "Save Zone" }, // Z inverted from backend (-25)
    "INTERNET_ZONE":     { center: new THREE.Vector3(-35, 0.1,   25), size: new THREE.Vector2( 5,  5), color: 0xB8860B, borderColor: 0xFFD700, label: "Internet Zone" }, // Z inverted from backend (-25)
    "WATER_COOLER_ZONE": { center: new THREE.Vector3( 30, 0.1,  -20), size: new THREE.Vector2( 4,  4), color: 0x4682B4, borderColor: 0x5F9EA0, label: "Water Cooler" }, // Z inverted from backend (20)
    "MEETING_ROOM_ZONE": { center: new THREE.Vector3(  0, 0.06,  15), size: new THREE.Vector2(15, 10), color: 0xAAAAAA }, // Z inverted from backend (-15)
    "IMAGE_GEN_ZONE":    { center: new THREE.Vector3(-20, 0.1,   25), size: new THREE.Vector2( 5,  5), color: 0xFF69B4, borderColor: 0xFF1493, label: "Image Gen Zone" }, // Z inverted from backend (-25)
    "CODE_EXEC_ZONE":    { center: new THREE.Vector3( 20, 0.1,   25), size: new THREE.Vector2( 5,  5), color: 0x8A2BE2, borderColor: 0x9932CC, label: "Code Exec Zone" }, // Z inverted from backend (-25)
    // Specialist Desk Zones from your app.js needed for AGENT_TARGET_DESK_POSITIONS below
    "HTML_DESK_ZONE":    { center: new THREE.Vector3( 20, 0.06, -15), size: new THREE.Vector2(10, 10), color: 0x9088AA }, // Z inverted from backend (15)
    "CSS_DESK_ZONE":     { center: new THREE.Vector3( 25, 0.06, -25), size: new THREE.Vector2(10, 10), color: 0x9088AA }, // Z inverted from backend (25)
    "JS_DESK_ZONE":      { center: new THREE.Vector3( 35, 0.06, -25), size: new THREE.Vector2(10, 10), color: 0x9088AA }, // Z inverted from backend (25)
};

// --- Agent Target Desk Positions (THREE.JS Coordinates) ---
// (Derived from ZONE_DEFINITIONS or specific if needed)
const AGENT_TARGET_DESK_POSITIONS = {
    "CEO": ZONE_DEFINITIONS["CEO_OFFICE"].center.clone().setY(0.5),
    // *** FIX PM/MKT to use their corrected zones ***
    "Product Manager": ZONE_DEFINITIONS["PM_DESK_ZONE"].center.clone().setY(0.5),
    "Marketer": ZONE_DEFINITIONS["MKT_DESK_ZONE"].center.clone().setY(0.5),
    // *** END FIX ***
    "Coder": ZONE_DEFINITIONS["CODER_DESK_ZONE"].center.clone().setY(0.5),
    "QA": ZONE_DEFINITIONS["QA_DESK_ZONE"].center.clone().setY(0.5),
    // Add Specialists if needed
    "HTML Specialist": ZONE_DEFINITIONS["HTML_DESK_ZONE"].center.clone().setY(0.5),
    "CSS Specialist": ZONE_DEFINITIONS["CSS_DESK_ZONE"].center.clone().setY(0.5),
    "JavaScript Specialist": ZONE_DEFINITIONS["JS_DESK_ZONE"].center.clone().setY(0.5),
    "Messenger": new THREE.Vector3(5, 0.5, 20), // Z inverted from backend (-20)
};

const MANAGER_MEETING_SPOTS = {
    "Product Manager": new THREE.Vector3(-3, 0.5, 21), // Z inverted from backend if needed, adjust if original Z was different
    "Marketer": new THREE.Vector3(3, 0.5, 21)       // Z inverted from backend if needed, adjust if original Z was different
};
// --- Scene Setup ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87CEEB);
scene.fog = new THREE.Fog(0xaaaaaa, 120, 300);
const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 2000);
camera.position.set(0, 80, 100 + 80);
camera.lookAt(0, 2, 0);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputEncoding = THREE.sRGBEncoding;
document.getElementById('simulation-container').appendChild(renderer.domElement);

// --- Lighting ---
scene.add(new THREE.AmbientLight(0x808080));
const directionalLight = new THREE.DirectionalLight(0xffffff, 0.9);
directionalLight.position.set(50, 70, 40); directionalLight.castShadow = true;
directionalLight.shadow.mapSize.width = 2048; directionalLight.shadow.mapSize.height = 2048;
directionalLight.shadow.camera.near = 1; directionalLight.shadow.camera.far = 200;
directionalLight.shadow.camera.left = -100; directionalLight.shadow.camera.right = 100;
directionalLight.shadow.camera.top = 100; directionalLight.shadow.camera.bottom = -100;
directionalLight.shadow.bias = -0.002; scene.add(directionalLight);

// --- Camera Controls ---
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.1;
controls.screenSpacePanning = true; controls.target.set(0, 2, 0);
controls.maxDistance = 400; controls.minDistance = 5; controls.maxPolarAngle = Math.PI / 2.05;

// --- Global State ---
let enabledToolZones = new Set(); // Stores the identifiers (values) of enabled zones

// --- Materials Cache ---
const materials = {
    floor: new THREE.MeshStandardMaterial({ color: 0x778899, roughness: 0.8 }),
    wall: new THREE.MeshStandardMaterial({ color: 0xF8F8FF, roughness: 0.9 }),
    partitionWall: new THREE.MeshStandardMaterial({ color: 0xDCDCDC, roughness: 0.8, metalness: 0.1 }),
    desk: new THREE.MeshStandardMaterial({ color: 0xD2B48C, roughness: 0.7 }),
    chair: new THREE.MeshStandardMaterial({ color: 0x555555, roughness: 0.6 }),
    ground: new THREE.MeshStandardMaterial({ color: 0x8BC34A, roughness: 1.0 }),
    path: new THREE.MeshStandardMaterial({ color: 0xAAAAAA, roughness: 0.9 }),
    treeTrunk: new THREE.MeshStandardMaterial({ color: 0x8B4513, roughness: 0.9 }),
    treeFoliage: new THREE.MeshStandardMaterial({ color: 0x2E8B57, roughness: 0.8 }),
    // Tool Zone Materials (generated dynamically based on ZONE_DEFINITIONS)
    zoneMaterials: {}, // Stores { 'ZONE_NAME': { area: ..., border: ... }, ... }
    ceoDesk: new THREE.MeshStandardMaterial({ color: 0x654321, roughness: 0.6 }),
    // Department Floor Materials (could be dynamic too)
    deptFloorBase: new THREE.MeshStandardMaterial({color: 0x8899AA, side: THREE.DoubleSide, roughness: 0.8}),
    deptFloorTech: new THREE.MeshStandardMaterial({color: 0x8090A0, side: THREE.DoubleSide, roughness: 0.8}),
    deptFloorCreative: new THREE.MeshStandardMaterial({color: 0x9088AA, side: THREE.DoubleSide, roughness: 0.8}),
};

// Function to get or create zone materials
function getZoneMaterial(zoneKey) {
    if (!materials.zoneMaterials[zoneKey]) {
        const zoneDef = ZONE_DEFINITIONS[zoneKey];
        if (!zoneDef) return null;
        materials.zoneMaterials[zoneKey] = {
            area: new THREE.MeshStandardMaterial({
                color: zoneDef.color || 0xCCCCCC,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.5,
                roughness: 0.8
            }),
            border: new THREE.LineBasicMaterial({
                color: zoneDef.borderColor || 0xFFFFFF,
                linewidth: 2 // Note: linewidth > 1 may not work on all systems/drivers
            })
        };
    }
    return materials.zoneMaterials[zoneKey];
}


// --- Environment Creation Functions ---
function createGroundAndPath() { const groundGeo = new THREE.PlaneGeometry(EXTERIOR_GROUND_SIZE, EXTERIOR_GROUND_SIZE); const ground = new THREE.Mesh(groundGeo, materials.ground); ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground); const pathWidth = 10; const pathGeo = new THREE.BoxGeometry(pathWidth, 0.1, EXTERIOR_GROUND_SIZE / 2); const path = new THREE.Mesh(pathGeo, materials.path); path.position.y = 0.05; path.position.z = BUILDING_DEPTH / 2 + EXTERIOR_GROUND_SIZE / 4; path.receiveShadow = true; scene.add(path); }
function createBuildingShell() { const wallThickness = 0.5; const halfW = BUILDING_WIDTH / 2; const halfD = BUILDING_DEPTH / 2; const wallY = WALL_HEIGHT / 2; const wallGroup = new THREE.Group(); const backWallGeo = new THREE.BoxGeometry(BUILDING_WIDTH, WALL_HEIGHT, wallThickness); const backWall = new THREE.Mesh(backWallGeo, materials.wall); backWall.position.set(0, wallY, -halfD + wallThickness/2); wallGroup.add(backWall); const doorWidth = 10; const doorHeight = 7; const frontWallSideW = (BUILDING_WIDTH - doorWidth) / 2; const frontWallGeo = new THREE.BoxGeometry(frontWallSideW, WALL_HEIGHT, wallThickness); const frontL = new THREE.Mesh(frontWallGeo, materials.wall); frontL.position.set(-(halfW - frontWallSideW / 2), wallY, halfD - wallThickness/2); wallGroup.add(frontL); const frontR = new THREE.Mesh(frontWallGeo, materials.wall); frontR.position.set( (halfW - frontWallSideW / 2), wallY, halfD - wallThickness/2); wallGroup.add(frontR); const lintelGeo = new THREE.BoxGeometry(doorWidth, WALL_HEIGHT - doorHeight, wallThickness); const lintel = new THREE.Mesh(lintelGeo, materials.wall); lintel.position.set(0, doorHeight + (WALL_HEIGHT - doorHeight)/2, halfD - wallThickness/2); wallGroup.add(lintel); const sideWallGeo = new THREE.BoxGeometry(BUILDING_DEPTH, WALL_HEIGHT, wallThickness); const leftWall = new THREE.Mesh(sideWallGeo, materials.wall); leftWall.position.set(-halfW + wallThickness/2, wallY, 0); leftWall.rotation.y = Math.PI / 2; wallGroup.add(leftWall); const rightWall = new THREE.Mesh(sideWallGeo, materials.wall); rightWall.position.set(halfW - wallThickness/2, wallY, 0); rightWall.rotation.y = Math.PI / 2; wallGroup.add(rightWall); wallGroup.children.forEach(wall => { wall.castShadow = true; wall.receiveShadow = true; }); scene.add(wallGroup); const floorGeo = new THREE.PlaneGeometry(BUILDING_WIDTH, BUILDING_DEPTH); const floor = new THREE.Mesh(floorGeo, materials.floor); floor.rotation.x = -Math.PI / 2; floor.position.y = 0.05; floor.receiveShadow = true; scene.add(floor); const ceilingGeo = new THREE.PlaneGeometry(BUILDING_WIDTH, BUILDING_DEPTH); const ceilingMat = materials.wall.clone(); ceilingMat.transparent = true; ceilingMat.opacity = 0.8; const ceiling = new THREE.Mesh(ceilingGeo, ceilingMat); ceiling.rotation.x = Math.PI / 2; ceiling.position.y = WALL_HEIGHT; scene.add(ceiling);}
function createDesk(position, rotationY = 0) { const group = new THREE.Group(); const deskGeo = new THREE.BoxGeometry(2.5, 0.15, 1.5); const desk = new THREE.Mesh(deskGeo, materials.desk); desk.position.y = 1.0; desk.castShadow = true; group.add(desk); const legGeo = new THREE.BoxGeometry(0.1, 1.0, 0.1); const legPositions = [{x:-1.1, z:-0.6}, {x:1.1, z:-0.6}, {x:-1.1, z:0.6}, {x:1.1, z:0.6}]; legPositions.forEach(p => { const leg = new THREE.Mesh(legGeo, materials.desk); leg.position.set(p.x, 0.5, p.z); group.add(leg); }); group.position.set(position.x, 0, position.z); group.rotation.y = rotationY; scene.add(group); return group; }
function createAgentDesks() { for (const role in AGENT_TARGET_DESK_POSITIONS) { if (role === "CEO") continue; const pos = AGENT_TARGET_DESK_POSITIONS[role]; if (pos && pos.isVector3) createDesk(new THREE.Vector3(pos.x, 0, pos.z)); } }
function createCEORoomContent() { const ceoZoneDef = ZONE_DEFINITIONS["CEO_OFFICE"]; const ceoDeskPos = AGENT_TARGET_DESK_POSITIONS["CEO"]; const longDeskGeo = new THREE.BoxGeometry(8, 0.2, 2.5); const longDesk = new THREE.Mesh(longDeskGeo, materials.ceoDesk); longDesk.position.set(ceoDeskPos.x, 1.0, ceoDeskPos.z); longDesk.castShadow = true; longDesk.receiveShadow = true; scene.add(longDesk); const ceoChairGeo = new THREE.BoxGeometry(0.9, 1.4, 0.9); const ceoChair = new THREE.Mesh(ceoChairGeo, materials.chair); ceoChair.position.set(ceoDeskPos.x, 0.7, ceoDeskPos.z + 1.5); ceoChair.castShadow = true; scene.add(ceoChair); const managerChairGeo = new THREE.BoxGeometry(0.7, 1.0, 0.7); const managerChairMat = materials.chair.clone(); managerChairMat.color.setHex(0x666666); Object.values(MANAGER_MEETING_SPOTS).forEach(spot => { if (spot && spot.isVector3) { const chair = new THREE.Mesh(managerChairGeo, managerChairMat); chair.position.copy(spot); chair.lookAt(longDesk.position.x, spot.y, longDesk.position.z); chair.castShadow = true; scene.add(chair); } }); }
function createTrees() { const trunkGeo = new THREE.CylinderGeometry(0.3, 0.4, 4, 8); const foliageGeo = new THREE.SphereGeometry(2.5, 8, 6); for (let i = 0; i < 35; i++) { const treeGroup = new THREE.Group(); const trunk = new THREE.Mesh(trunkGeo, materials.treeTrunk); trunk.position.y = 2; trunk.castShadow = true; treeGroup.add(trunk); const foliage = new THREE.Mesh(foliageGeo, materials.treeFoliage); foliage.position.y = 5; foliage.castShadow = true; treeGroup.add(foliage); let x, z; do { x = Math.random() * EXTERIOR_GROUND_SIZE - EXTERIOR_GROUND_SIZE / 2; z = Math.random() * EXTERIOR_GROUND_SIZE - EXTERIOR_GROUND_SIZE / 2; } while (Math.abs(x) < BUILDING_WIDTH / 2 + 5 && Math.abs(z) < BUILDING_DEPTH / 2 + 5); treeGroup.position.set(x, 0, z); scene.add(treeGroup); } }

// --- NEW: Function to create a generic visual zone ---
function createVisualZone(zoneKey) {
    const zoneDef = ZONE_DEFINITIONS[zoneKey];
    if (!zoneDef) {
        console.warn(`Definition not found for zone key: ${zoneKey}`);
        return;
    }
    const mats = getZoneMaterial(zoneKey);
    if (!mats) {
        console.warn(`Materials not found for zone key: ${zoneKey}`);
        return;
    }

    const zoneSize = zoneDef.size; // Vector2(width, depth)
    const zoneCenter = zoneDef.center; // Vector3

    // Area Plane
    const areaGeo = new THREE.PlaneGeometry(zoneSize.x, zoneSize.y);
    const areaMesh = new THREE.Mesh(areaGeo, mats.area);
    areaMesh.rotation.x = -Math.PI / 2;
    areaMesh.position.copy(zoneCenter);
    areaMesh.receiveShadow = true; // Zones can receive shadows
    areaMesh.userData = { isInteractiveZone: true, zoneId: zoneKey, label: zoneDef.label || zoneKey };
    scene.add(areaMesh);

    // Border Line
    const halfW = zoneSize.x / 2;
    const halfD = zoneSize.y / 2;
    const borderPoints = [
        new THREE.Vector3(-halfW, 0, -halfD), new THREE.Vector3( halfW, 0, -halfD),
        new THREE.Vector3( halfW, 0,  halfD), new THREE.Vector3(-halfW, 0,  halfD),
        new THREE.Vector3(-halfW, 0, -halfD) // Close the loop
    ];
    const borderGeo = new THREE.BufferGeometry().setFromPoints(borderPoints);
    const borderLine = new THREE.Line(borderGeo, mats.border);
    borderLine.position.copy(zoneCenter);
    borderLine.position.y += 0.02; // Slightly above the plane
    scene.add(borderLine);

    // Optional: Add specific objects like a water cooler model
    if (zoneKey === 'WATER_COOLER_ZONE') {
        const coolerGeo = new THREE.CylinderGeometry(0.4, 0.4, 1.2, 12);
        const coolerMat = new THREE.MeshStandardMaterial({ color: 0xe0f8ff, roughness: 0.3 });
        const coolerMesh = new THREE.Mesh(coolerGeo, coolerMat);
        coolerMesh.position.copy(zoneCenter);
        coolerMesh.position.y = 0.6;
        coolerMesh.castShadow = true;
        scene.add(coolerMesh);
    }

     // Optional: Add visual cues for other zones if desired (e.g., antenna for internet)
     if (zoneKey === 'INTERNET_ZONE') {
          const antennaBaseGeo = new THREE.CylinderGeometry(0.2, 0.2, 0.5, 8);
          const antennaMastGeo = new THREE.CylinderGeometry(0.05, 0.05, 1.5, 8);
          const antennaMat = new THREE.MeshStandardMaterial({ color: 0xAAAAAA, metalness: 0.5 });
          const base = new THREE.Mesh(antennaBaseGeo, antennaMat);
          base.position.copy(zoneCenter);
          base.position.y = 0.25;
          base.castShadow = true;
          scene.add(base);
          const mast = new THREE.Mesh(antennaMastGeo, antennaMat);
          mast.position.copy(zoneCenter);
          mast.position.y = 0.5 + 1.5/2; // Position on top of base
          mast.castShadow = true;
          scene.add(mast);
      }
    // Add visual representations for IMAGE_GEN_ZONE, CODE_EXEC_ZONE here if desired

    console.log(`Created visual zone: ${zoneKey}`);
}

// --- Build Static Environment ---
function buildStaticEnvironment() {
    createGroundAndPath();
    createBuildingShell();
    createAgentDesks();
    createCEORoomContent();
    createTrees();
    // Department floor zones (can also be made conditional if needed)
    for (const key in ZONE_DEFINITIONS) {
        // Create dept floors based on some logic, e.g., if they don't have specific border/tool props
        const zoneDef = ZONE_DEFINITIONS[key];
        if (zoneDef && !zoneDef.borderColor && !key.includes("DESK") && key !== "MEETING_ROOM_ZONE") {
             const deptFloorGeo = new THREE.PlaneGeometry(zoneDef.size.x, zoneDef.size.y);
             let floorMat = materials.deptFloorBase.clone(); // Add logic for different dept colors if desired
             const deptFloor = new THREE.Mesh(deptFloorGeo, floorMat);
             deptFloor.rotation.x = -Math.PI / 2;
             deptFloor.position.copy(zoneDef.center);
             deptFloor.receiveShadow = true;
             scene.add(deptFloor);
        }
    }

}
buildStaticEnvironment(); // Build the non-conditional parts

// --- Build Conditional Tool Zones ---
function buildToolZones() {
    console.log("Building tool zones based on enabled set:", enabledToolZones);
    for (const zoneKey of enabledToolZones) {
         if (ZONE_DEFINITIONS[zoneKey]) {
             createVisualZone(zoneKey);
         } else {
             console.warn(`No definition found for enabled zone: ${zoneKey}`);
         }
    }
}
// buildToolZones() called later by start button handler

// --- Agent Management ---
const agentMeshes = {}; const agentGeometryCache = {}; const agentMaterialCache = {};
function getAgentGeometry(role) { if (agentGeometryCache[role]) return agentGeometryCache[role].clone(); let geometry; let heightOffset = 0.75; if (role === 'CEO') { geometry = new THREE.CylinderGeometry(0.5, 0.5, 1.8, 12); heightOffset = 1.8 / 2; } else if (role === 'Coder' || role === 'QA') { geometry = new THREE.BoxGeometry(0.8, 1.5, 0.8); heightOffset = 1.5 / 2; } else if (role === 'Product Manager') { geometry = new THREE.ConeGeometry(0.7, 1.8, 8); heightOffset = 1.8 / 2; } else if (role === 'Marketer') { geometry = new THREE.CylinderGeometry(0.5, 0.7, 1.6, 8); heightOffset = 1.6 / 2; } else if (role === 'Messenger') { geometry = new THREE.SphereGeometry(0.6, 16, 8); heightOffset = 0.6;} else { geometry = new THREE.SphereGeometry(0.7, 16, 8); heightOffset = 0.7; } geometry.translate(0, heightOffset, 0); agentGeometryCache[role] = geometry; return geometry.clone(); }
function getAgentMaterial(role) { if(agentMaterialCache[role])return agentMaterialCache[role].clone(); let color; if(role==="CEO")color=0xff4444;else if(role==="Product Manager")color=0x44ff44;else if(role==="Coder")color=0x4444ff;else if(role==="Marketer")color=0xffff44; else if(role==="QA")color=0x44ffff; else if(role==="Messenger")color=0xff8844; else color=0xaaaaaa; const mat=new THREE.MeshStandardMaterial({color:color,roughness:0.6,metalness:0.2, emissive: 0x000000});agentMaterialCache[role]=mat;return mat.clone(); }
function createTextLabel(text) { const canvas=document.createElement('canvas');const context=canvas.getContext('2d');const fontSize=24;context.font=`Bold ${fontSize}px Arial`;const textWidth=context.measureText(text).width;canvas.width=textWidth+20;canvas.height=fontSize+10;context.font=`Bold ${fontSize}px Arial`;context.fillStyle='rgba(0,0,0,0.7)';context.fillRect(0,0,canvas.width,canvas.height);context.fillStyle='white';context.textAlign='center';context.textBaseline='middle';context.fillText(text,canvas.width/2,canvas.height/2);const texture=new THREE.CanvasTexture(canvas);texture.needsUpdate=true;const spriteMaterial=new THREE.SpriteMaterial({map:texture,depthTest:false,transparent:true});const sprite=new THREE.Sprite(spriteMaterial);const desiredLabelHeight=0.4;sprite.scale.set((desiredLabelHeight*canvas.width)/canvas.height,desiredLabelHeight,1);sprite.position.y=2.2;return sprite; }

// --- WebSocket Connection & Handlers ---
const socket = io();
socket.on('connect', () => { console.log(`Connected with ID: ${socket.id}`); });
socket.on('connect_error', (err) => { console.error('WS Connect Error:', err); alert(`Connection Error: ${err.message}`);});
socket.on('disconnect', (reason) => { console.log(`Disconnected. Reason: ${reason}`); });

socket.on('update_agent', (data) => {
    // --- START DEBUG ---
    console.log(`[DEBUG] Received update_agent event for agent: ${data?.agent_id}`);
    // Log the entire state object received to check for the role property
    console.log(`[DEBUG] Received state object:`, data?.state);
    // --- END DEBUG ---

    const agentId = data.agent_id;
    const state = data.state;

    // More robust check for state object
    if (!state || typeof state !== 'object') {
        console.error(`Invalid or missing state received for agent ${agentId}:`, state);
        return;
    }

    if (!agentMeshes[agentId]) { // Create Agent
        // --- START DEBUG ---
        console.log(`[DEBUG] Attempting to create agent ${agentId}. Checking state.role...`);
        // --- END DEBUG ---
        // MODIFIED CHECK: Ensure role is a non-empty string before proceeding
        if (!state.role || typeof state.role !== 'string' || state.role.trim() === '') {
            // --- START DEBUG ---
            // Log the state again specifically when the role check fails
            console.error(`[DEBUG] Role check failed for agent ${agentId}. Received state:`, state);
            // --- END DEBUG ---
            console.error(`No valid role found for new agent ${agentId}`); // Keep original error
            return; // This prevents agent creation if role isn't valid *in this specific message*
        }
        // If role is valid, proceed with creation...
        const geometry = getAgentGeometry(state.role);
        const material = getAgentMaterial(state.role);
        const agentMesh = new THREE.Mesh(geometry, material);
        agentMesh.castShadow = true;
        agentMesh.receiveShadow = true;

        const agentName = `${state.role} (${agentId.split('-')[1] || 'ID'})`;
        const label = createTextLabel(agentName);
        agentMesh.add(label);

        let initialPos = new THREE.Vector3(0, 0.5, 0); // Default pos
        // Use backend position including Y, invert Z
        if (state.position && Array.isArray(state.position) && state.position.length === 3) {
            // Use initialPos directly instead of undefined agentData
            initialPos.set(state.position[0], state.position[1], -state.position[2]);
        } else { console.warn(`Agent ${agentId} created without valid initial pos.`); }
        agentMesh.position.copy(initialPos);

        scene.add(agentMesh);
        agentMesh.userData = { isAgent: true, id: agentId };
        agentMeshes[agentId] = {
            mesh: agentMesh,
            targetPosition: agentMesh.position.clone(), // Use agentMesh's current position
            role: state.role,
            name: agentName,
            thoughts: state.current_thoughts || '...',
            status: state.status || 'idle',
             label: label
            };
        console.log(`Created agent ${agentId} (${state.role}) at ${initialPos.x.toFixed(1)}, ${initialPos.y.toFixed(1)}, ${initialPos.z.toFixed(1)}`); // Log creation success
    } else { // Update Agent
        const agentData = agentMeshes[agentId];
        const mesh = agentData.mesh;

        // Update target position using backend data (including Y)
        if (state.position && Array.isArray(state.position) && state.position.length === 3) {
             // Invert Z coordinate from backend, use backend Y
            agentData.targetPosition.set(state.position[0], state.position[1], -state.position[2]);
        }

        // Update thoughts and status/emissive color
        if (state.current_thoughts !== undefined) { agentData.thoughts = state.current_thoughts; }
        if (state.status !== undefined && agentData.status !== state.status) {
            // console.log(`Agent ${agentId} status changed to ${state.status}`); // Reduce log noise
            agentData.status = state.status;
            let emissiveColor = 0x000000; // Default off
            switch(state.status) { // Use new status constants if available
                case 'working': emissiveColor = 0x003300; break; // STATUS_WORKING
                case 'waiting_user_input':                // STATUS_WAITING_RESPONSE (for user)
                case 'waiting_response': emissiveColor = 0x442200; break;
                case 'failed': emissiveColor = 0x550000; break; // STATUS_FAILED
                case 'moving_to_zone': emissiveColor = 0x333300; break; // STATUS_MOVING_TO_ZONE
                case 'meeting': emissiveColor = 0x000055; break; // STATUS_MEETING
                case 'using_tool_in_zone': emissiveColor = 0x005555; break; // STATUS_USING_TOOL_IN_ZONE
                case 'idle':
                     const idleSubState = state.current_idle_sub_state; // Check sub-state
                     if (idleSubState === 'at_water_cooler') emissiveColor = 0x004488;
                     else if (idleSubState === 'wandering') emissiveColor = 0x331133;
                     else emissiveColor = 0x111111; // Default idle/at desk
                     break;
                 default: emissiveColor = 0x000000; // Off for unknown states
            }
            // Ensure material exists and is the correct type before setting emissive
             if (mesh.material && typeof mesh.material.emissive !== 'undefined') {
                  mesh.material.emissive.setHex(emissiveColor);
             }
        }
    }
});
socket.on('remove_agent', (data) => { if(!data || !data.agent_id) return; const agentId = data.agent_id; if (agentMeshes[agentId]) { scene.remove(agentMeshes[agentId].mesh); delete agentMeshes[agentId]; console.log(`Removed agent ${agentId}`); } });
socket.on('simulation_complete', (data) => { console.log('Simulation Complete:', data); alert(`Simulation Complete!\nSuccess: ${data.success}\nOutput: ${data.output}`); const configPanels = document.getElementById('config-panels-container'); const startButtonCont = document.getElementById('start-button-container'); if(configPanels) configPanels.classList.remove('hidden'); if(startButtonCont) startButtonCont.classList.remove('hidden');});
socket.on('request_user_input', (data) => { const response = prompt(`Input Required for Task ${data.task_id}:\n${data.question}`); if (response !== null) { socket.emit('user_response', { task_id: data.task_id, response: response }); } else { console.log('User cancelled input request.'); } });
socket.on('simulation_status', (data) => { console.log('Simulation Status:', data.status); if(data.status === 'error') alert(`Simulation Error: ${data.message || 'Unknown error'}`); });
socket.on('simulation_error', (data) => { console.error('Simulation Error from Backend:', data.error); alert(`Simulation Error: ${data.error}`); const configPanels = document.getElementById('config-panels-container'); const startButtonCont = document.getElementById('start-button-container'); if(configPanels) configPanels.classList.remove('hidden'); if(startButtonCont) startButtonCont.classList.remove('hidden'); });


// --- UI Interaction ---
const startButton = document.getElementById('start-button');
const configPanelsContainer = document.getElementById('config-panels-container');
const startButtonContainer = document.getElementById('start-button-container');
const agentRoles = ["CEO", "Product Manager", "Coder", "Marketer", "QA"]; // Add QA

startButton.addEventListener('click', () => {
    // 1. Collect LLM Configs
    const llmConfigs = {};
    let llmConfigIsValid = true;
    agentRoles.forEach(role => {
        const roleId = role.toLowerCase().replace(/ /g, '');
        const typeElement = document.getElementById(`${roleId}-type`);
        const modelElement = document.getElementById(`${roleId}-model`);
        if (!typeElement || !modelElement) {
             if (role !== "Messenger") {
                  console.warn(`UI elements for LLM config not found for role: ${role}`);
             }
             return;
         }
        const type = typeElement.value;
        const model = modelElement.value.trim() || null;
        if (!type && role !== "Messenger") {
            console.error(`LLM type not selected for role: ${role}`);
            llmConfigIsValid = false;
        }
        llmConfigs[role] = { type: type, model: model };
    });

    if (!llmConfigIsValid) {
        alert("Please ensure an LLM provider is selected for all agent roles (except Messenger).");
        return;
    }

    // 2. Collect Enabled Tool Zones
    enabledToolZones = new Set(); // Reset before collecting
    const toolCheckboxes = document.querySelectorAll('#tool-config-panel input[type="checkbox"]');
    toolCheckboxes.forEach(checkbox => {
        if (checkbox.checked) {
            enabledToolZones.add(checkbox.value);
        }
    });
    console.log("Enabled Tool Zones:", Array.from(enabledToolZones));

    // 3. Get User Request
    const userRequest = prompt("Enter the high-level project request:", "Create a basic webpage about cars");

    // 4. Start Simulation if request provided
    if (userRequest) {
        console.log(`Sending start_simulation event with request: ${userRequest}`);
        console.log("LLM Configs:", llmConfigs);
        console.log("Enabled Tools/Zones:", Array.from(enabledToolZones));

        // Build the visual tool zones based on selection
        // TODO: Add logic here to *remove* old zone meshes if simulation is restarting
        buildToolZones();

        // Emit start event with all collected configs
        socket.emit('start_simulation', {
            request: userRequest,
            llm_configs: llmConfigs,
            enabled_tools: Array.from(enabledToolZones) // Send enabled zones to backend
        });

        // Hide configuration UI
        if (configPanelsContainer) configPanelsContainer.classList.add('hidden');
        if (startButtonContainer) startButtonContainer.classList.add('hidden');

    } else {
        console.log("User cancelled the project request input.");
    }
});


// --- Window Resize & Mouse Hover ---
function onWindowResize() { camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth, window.innerHeight); } window.addEventListener('resize', onWindowResize, false); const raycaster = new THREE.Raycaster(); const mouse = new THREE.Vector2(); let hoverInfoElement = null; let interactiveObjects = []; function updateInteractiveObjectsList() { interactiveObjects = []; Object.values(agentMeshes).forEach(data => { if (data.mesh) interactiveObjects.push(data.mesh); }); scene.traverse((obj) => { if (obj.isMesh && obj.userData.isInteractiveZone) { if (!interactiveObjects.includes(obj)) interactiveObjects.push(obj); } }); } function updateHoverInfo(event) { mouse.x=(event.clientX/window.innerWidth)*2-1; mouse.y=-(event.clientY/window.innerHeight)*2+1; raycaster.setFromCamera(mouse, camera); updateInteractiveObjectsList(); const intersects = raycaster.intersectObjects(interactiveObjects); if(hoverInfoElement){hoverInfoElement.remove(); hoverInfoElement=null; document.body.style.cursor='default';} if(intersects.length > 0){ const firstIntersect = intersects[0]; const obj = firstIntersect.object; let hoverText = null; let objName = "Object"; if(obj.userData.isAgent){ let agentData = null; for(const id in agentMeshes){if(agentMeshes[id].mesh===obj){agentData=agentMeshes[id]; break;}} if(agentData){ objName = agentData.name; hoverText = `<b>${agentData.name}</b><br>Status: ${agentData.status}<br>Thoughts: ${agentData.thoughts}`; } } else if(obj.userData.isInteractiveZone){ objName = obj.userData.label || "Zone"; hoverText = `<b>${objName}</b>`; } if(hoverText){ document.body.style.cursor='pointer'; hoverInfoElement=document.createElement('div'); hoverInfoElement.style.position = 'absolute'; hoverInfoElement.style.left = `${event.clientX + 15}px`; hoverInfoElement.style.top = `${event.clientY + 15}px`; hoverInfoElement.style.padding = '8px'; hoverInfoElement.style.background = 'rgba(0,0,0,0.8)'; hoverInfoElement.style.color = 'white'; hoverInfoElement.style.borderRadius = '4px'; hoverInfoElement.style.pointerEvents = 'none'; hoverInfoElement.style.fontFamily = 'sans-serif'; hoverInfoElement.style.fontSize = '12px'; hoverInfoElement.style.maxWidth = '300px'; hoverInfoElement.innerHTML = hoverText; document.body.appendChild(hoverInfoElement); } } } window.addEventListener('mousemove', updateHoverInfo, false);


// --- Animation Loop ---
const clock = new THREE.Clock();
const direction = new THREE.Vector3();
function animate() {
    requestAnimationFrame(animate);
    const deltaTime = Math.min(clock.getDelta(), 0.1); // Clamp delta time
    controls.update(); // Required if damping enabled

    // Agent movement logic
    for (const agentId in agentMeshes) {
        const agentData = agentMeshes[agentId];
        const mesh = agentData.mesh;
        const targetPos = agentData.targetPosition;

        if (mesh && targetPos && mesh.position) { // Ensure all refs are valid
            const distance = mesh.position.distanceTo(targetPos);

            if (distance > 0.01) { // Move if not already at target
                direction.subVectors(targetPos, mesh.position).normalize();
                let moveStep = AGENT_MOVEMENT_SPEED * deltaTime;
                // Clamp moveStep to prevent overshooting
                moveStep = Math.min(moveStep, distance);
                mesh.position.addScaledVector(direction, moveStep);

                // Make agent look towards movement direction (Y-axis up)
                const lookAtTarget = new THREE.Vector3().addVectors(mesh.position, direction);
                lookAtTarget.y = mesh.position.y; // Keep looking level
                if (lookAtTarget.distanceTo(mesh.position) > 0.01) {
                   mesh.lookAt(lookAtTarget);
                }
            }
        }
    }
    renderer.render(scene, camera);
}
animate(); // Start the animation loop