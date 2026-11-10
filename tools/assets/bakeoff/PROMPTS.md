# Image-generation record

All four generations used Codex's built-in `image_gen` with the real reference
photos attached. The surface did not expose a billable price or exact model
version. Files preserve the selected pixels; prompt replay is not deterministic.
No paid OpenAI API-key fallback or external 3D API was used.

## C — one shared material atlas

References, in order: bungalow, storefront, apartment photographs from
`results/references.json`. `transparent_background=false`.

> Create a square 1024x1024 game-material texture atlas for the three attached Asheville building references. This is an unlit diffuse/albedo material asset, NOT a picture of a building and NOT a comparison diagram. Divide the entire square into exactly four equal square quadrants, no gutters, no labels, no borders. Upper-left: pale warm yellow painted narrow horizontal timber clapboard siding, weathered subtly like the Norwood bungalow reference. Upper-right: authentic warm red-brown old Asheville running-bond brick with gray-tan mortar, like Lexington and Hillcrest references, modest local irregularities not exaggerated ruined bricks. Lower-left: dark charcoal gray asphalt shingles in subtly staggered horizontal courses, like the apartment roof reference. Lower-right: gray-brown Appalachian rough stone foundation wall. Every quadrant is an orthographic flat material surface facing the camera exactly, edges seamless within its material; no perspective, no cast shadows, no highlights, no ambient occlusion, neutral even light. No windows, no doors, no plants, no written text. Realistic fine surface detail, balanced game asset contrast. Preserve these four exact positions because code slices them into UV material tiles.

The tool returned a 1254-square image rather than the requested size.
`materials.py` splits the actual quadrants, resizes tiles, and bakes explicit
1024-square main maps; it never assumes the generator obeyed the size request.

## B1 — three photo-informed concept controls

One call per target with its corresponding real photograph.
`transparent_background=false`. Each complete prompt is the following prefix,
its target paragraph, then the suffix below, concatenated with spaces.

Prefix:

> Use case: stylized-concept. Asset type: clean reference image for image-to-3D building reconstruction. Generate ONE isolated complete 3D building as a photoreal architectural product view, based on the attached real photograph.

Bungalow:

> a 1920s Asheville Craftsman bungalow closely matching 108 Norwood Avenue in the reference: pale yellow narrow clapboard siding, white trim, broad full-width deep porch with white square posts and simple railings, centered entry and 4 front steps, substantial gray shingle side-gable roof with broad front-gabled dormer and 3 dormer windows, brick chimney, stone foundation. Preserve the proportions, character and roof style of the reference. Plausible full house depth about 12m and width10.5m, height7m.

Storefront:

> a single complete 1920s red brick downtown Asheville Lexington Avenue three-story shop building, 8m wide by15mdeep, height11.3m. Use the left shopfront's architectural character in the reference: red-brown brick, 3 tall paired sash window bays on each of the two upper stories, recessed ground-floor glazed shopfront with centered wood door, dark blue awning, restrained cornice and parapet, dark flat roof behind the parapet. Preserve that regional building's character, not the tree or adjacent shops.

Apartment:

> a complete long two-story Hillcrest-style Asheville red brick townhome apartment block, 28mwide by10mdeep, height8.3m. Preserve the reference's current architecture: red brick, cream panels and trim on upper facade, charcoal shingle pitched main roof with cross-gabled sections, repeated small front-gabled porch entrances with white posts, simple double-hung windows. Four repeated entry bays, long continuous brick rear mass. This is Asheville Hillcrest, not a historic apartment from another city.

Suffix:

> Camera at modest elevation showing the full FRONT and RIGHT side and the roof, moderate orthographic-like perspective, all parts unobstructed and inside the frame with 10% white margin. Flat pure white background, no ground plane, no cast shadow, neutral diffuse studio light. No trees, shrubs, grass, neighboring buildings, people, vehicles, power lines, signs, words or labels. No slice, no cutaway, no cross-section, no diorama base. Every facade must be real coherent building geometry; no front-photo texture slapped onto a box. Keep simple realistic weathering, not derelict. The photograph informs the architecture; unseen surfaces are explicitly an artistic reconstruction, not a survey.

These outputs are synthetic interpretations. They do not establish hidden
facades, roof dimensions, exact window counts or correspondence to one real lot.
