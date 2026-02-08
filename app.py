import streamlit as st
import face_recognition
import io
import os
import cv2
from PIL import Image
from googleapiclient.http import MediaIoBaseDownload
from drive_auth import get_drive_service

# --- 1. PAGE CONFIG & PASTEL CSS ---
st.set_page_config(
    page_title="Photo Finder", 
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Pastel Color Palette & Styling
st.markdown("""
<style>
    /* Main Background: Soft Lavender */
    .stApp {
        background-color: #F3E5F5;
    }

    /* Sidebar: Soft Pink */
    [data-testid="stSidebar"] {
        background-color: #F8BBD0;
    }

    /* Content Containers: Soft Light Blue with black text */
    .block-container {
    background-color: #ebf8ff; 
    color: #000000; /* Ensures text is solid black */
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 90%;
    border-radius: 8px; 
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); /* Softened the shadow for the lighter bg */
}

    /* Buttons: Pastel Blue/Pink */
    div.stButton > button:first-child {
        background-color: #90CAF9;
        color: #1A237E;
        border-radius: 50px;
        padding: 10px 30px;
        font-weight: bold;
        border: 2px solid #ffffff;
        width: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    div.stButton > button:first-child:hover {
        background-color: #64B5F6;
        transform: translateY(-2px);
    }
    
    /* Clean text */
    h1, h2, h3 {
        color: #4A148C;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. HELPER FUNCTIONS ---

def extract_folder_id(url):
    """Extracts the Folder ID from a Google Drive URL."""
    try:
        if "folders/" in url:
            return url.split("folders/")[1].split("?")[0]
        elif "/view" in url:
            return url.split("/")[5]
        return url
    except:
        return None

def load_image_from_drive(service, file_id):
    """Downloads a file from Drive into memory."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0) 
    return fh.read()

# --- 3. SESSION STATE ---
if 'found_images' not in st.session_state:
    st.session_state.found_images = []
if 'scan_done' not in st.session_state:
    st.session_state.scan_done = False
if 'page' not in st.session_state:
    st.session_state.page = 1
if 'ref_encoding' not in st.session_state:
    st.session_state.ref_encoding = None

# --- 4. SIDEBAR (CONTROLS) ---
with st.sidebar:
    st.markdown("### 📷 Step 1: Your Face")
    st.info("Take a selfie so we know who to look for.")
    camera_image = st.camera_input("Capture Face", key="camera")
    
    if camera_image:
        # Detect face just to confirm it works for the user
        img = face_recognition.load_image_file(camera_image)
        face_locations = face_recognition.face_locations(img, model="hog")
        
        if len(face_locations) > 0:
            # Draw a small visual confirmation box (only for the preview)
            opencv_img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            top, right, bottom, left = face_locations[0]
            cv2.rectangle(opencv_img, (left, top), (right, bottom), (255, 105, 180), 4) # Pink box
            rgb_img = cv2.cvtColor(opencv_img, cv2.COLOR_BGR2RGB)
            
            st.image(rgb_img, caption="Face Detected! ✨", use_container_width=True)
            
            encodings = face_recognition.face_encodings(img, face_locations)
            if len(encodings) > 0:
                st.session_state.ref_encoding = encodings[0]
        else:
            st.error("No face detected. Try again.")

    st.markdown("---")
    st.markdown("### 🔗 Step 2: Album Link")
    folder_link = st.text_input("Paste Drive Link")
    
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    tolerance = st.slider("Accuracy", 0.4, 0.6, 0.5, 0.01)
    model_type = st.selectbox("Speed vs Detail", ["hog (Fast)", "cnn (Slow/Detailed)"])
    # Select box returns string, fix logic later
    
    st.markdown("---")
    scan_button = st.button("🚀 Find My Photos")

# --- 5. MAIN LAYOUT ---

st.title("🌸 Your Photo Finder")
st.markdown("We'll scan the album and bring back the **clean, original photos** of you.")

# --- 6. SCANNING LOGIC ---
if scan_button:
    if st.session_state.ref_encoding is None:
        st.toast("Please take a selfie first!", icon="📷")
    elif not folder_link:
        st.toast("Please paste a link!", icon="🔗")
    else:
        my_face_encoding = st.session_state.ref_encoding
        
        # Fix model selection logic
        use_cnn = True if "cnn" in model_type else False
        
        st.toast("Scanning... this may take a moment ☕", icon="⏳")
        
        try:
            service = get_drive_service()
            folder_id = extract_folder_id(folder_link)
            
            if not folder_id:
                st.error("Invalid Google Drive Link.")
            else:
                query = f"'{folder_id}' in parents and mimeType contains 'image/'"
                
                results = service.files().list(
                    q=query,
                    pageSize=100, 
                    fields="nextPageToken, files(id, name)"
                ).execute()
                
                items = results.get('files', [])
                
                # Pagination
                while 'nextPageToken' in results:
                    page_token = results['nextPageToken']
                    results = service.files().list(
                        q=query,
                        pageSize=100,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name)"
                    ).execute()
                    items.extend(results.get('files', []))
                
                if not items:
                    st.warning("No images found in that folder.")
                else:
                    progress_bar = st.progress(0)
                    found_count = 0
                    
                    for index, item in enumerate(items):
                        file_id = item['id']
                        name = item['name']
                        
                        try:
                            file_bytes = load_image_from_drive(service, file_id)
                            
                            # We read the image ONLY to detect faces
                            image = face_recognition.load_image_file(io.BytesIO(file_bytes))
                            
                            face_locations = face_recognition.face_locations(image, model=use_cnn, number_of_times_to_upsample=1)
                            face_encodings = face_recognition.face_encodings(image, face_locations)
                            
                            found_me = False
                            
                            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                                matches = face_recognition.compare_faces([my_face_encoding], face_encoding, tolerance=tolerance)
                                
                                if True in matches:
                                    found_me = True
                                    break
                            
                            # --- SAVING ORIGINAL IMAGE ---
                            if found_me:
                                # We append the ORIGINAL file_bytes, not the modified one
                                st.session_state.found_images.append((file_bytes, name))
                                found_count += 1
                                
                        except Exception as e:
                            pass 

                        progress_bar.progress((index + 1) / len(items))
                    
                    st.session_state.scan_done = True
                    st.toast(f"Done! Found {found_count} photos 🎉", icon="✨")
                    st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# --- 7. CLEAN GALLERY (NO BOXES) ---
if st.session_state.scan_done:
    st.divider()
    
    if not st.session_state.found_images:
        st.markdown("<div style='text-align:center; padding: 2rem;'><h3>No photos found 😔</h3><p>Try adjusting the accuracy slider.</p></div>", unsafe_allow_html=True)
    else:
        # Header
        col_count, col_page = st.columns([2, 1])
        with col_count:
            st.header(f"🖼️ {len(st.session_state.found_images)} Photos Found")
        with col_page:
            st.info("Downloading these saves the clean originals.")
        
        # Pagination
        items_per_page = 12
        total_pages = (len(st.session_state.found_images) // items_per_page) + 1
        
        col_prev, col_text, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("⬅️ Prev", disabled=(st.session_state.page <= 1)):
                st.session_state.page -= 1
                st.rerun()
        with col_text:
            st.markdown(f"<h4 style='text-align: center; margin-top: 25px;'>Page {st.session_state.page} of {total_pages}</h4>", unsafe_allow_html=True)
        with col_next:
            if st.button("Next ➡️", disabled=(st.session_state.page >= total_pages)):
                st.session_state.page += 1
                st.rerun()
        
        # Grid Layout (3 Columns)
        start_idx = (st.session_state.page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        current_batch = st.session_state.found_images[start_idx:end_idx]
        
        for i in range(0, len(current_batch), 3):
            cols = st.columns(3)
            for col_idx in range(3):
                if i + col_idx < len(current_batch):
                    file_bytes, filename = current_batch[i + col_idx]
                    with cols[col_idx]:
                        # Card Style for each image
                        st.markdown("""
                        <div style="background: white; padding: 10px; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                        """, unsafe_allow_html=True)
                        
                        # Display ORIGINAL Image
                        st.image(file_bytes, use_container_width=True)
                        st.caption(filename)
                        
                        st.download_button(
                            label="⬇️ Download",
                            data=file_bytes,
                            file_name=filename,
                            mime="image/jpeg",
                            key=f"dl_{filename}",
                            use_container_width=True
                        )
                        
                        st.markdown("</div>", unsafe_allow_html=True)