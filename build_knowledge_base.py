from knowledge.data_ingestion import DexKitKnowledgeBase

# Complete list of DexKit tutorial videos
YOUTUBE_URLS = [
    "https://youtu.be/pvzGTxcebW4",
    "https://youtu.be/U9NuKoqdFxk",
    "https://youtu.be/Z6v4xBG6TtQ",
    "https://youtu.be/5TVhUmg-sbc",
    "https://youtu.be/cK10-fd4eGM",
    "https://youtu.be/Uhu0VipVBzE",
    "https://youtu.be/gqpGiA04qIU",
    "https://youtu.be/f5KRmhEW4aw",
    "https://youtu.be/4ShlkaUDQms",
    "https://youtu.be/Oo3agVVp0NM",
    "https://youtu.be/42EV5wDH-l4",
    "https://youtu.be/z-IGYnsXCtQ",
    "https://youtu.be/FuFtQRrbcM4",
    "https://youtu.be/UIpAsOQtVi8",
    "https://youtu.be/X7TCt0VCv20",
    "https://youtu.be/R4O3mL_ZTi4",
    "https://youtu.be/FV832caR6MU",
    "https://youtu.be/A8Kl_20hZDU",
    "https://youtu.be/eexn_26EBJA",
    "https://youtu.be/36pmIP7qvg8",
    "https://youtu.be/4Ex-wV8DWgk",
    "https://youtu.be/fXppwjRqVpM",
    "https://youtu.be/dx_2PU6JRlw",
    "https://youtu.be/rXSekAW4YD4",
    "https://youtu.be/iLHgctqdaT8",
    "https://youtu.be/0D00j-KIJ00",
    "https://youtu.be/0IP1tZZ3KVw",
    "https://youtu.be/mnGlv7l_E24",
    "https://youtu.be/KJle-Q_qK5Y",
    "https://youtu.be/ZofvecpJiVE",
    "https://youtu.be/LxPa5iuk1R4",
    "https://youtu.be/uMivD0Rikg8",
    "https://youtu.be/yhVF6WtZd2A",
    "https://youtu.be/9Xr22V6smiY",
    "https://youtu.be/zNn0KG56Tkc",
    "https://youtu.be/g-1H4KyODWU",
    "https://youtu.be/aL7apwnXNZs",
    "https://youtu.be/GpFpBxPHbcA",
    "https://youtu.be/ppKPqthUTLs",
    "https://youtu.be/M0vnoVX6rwg",
    "https://youtu.be/1s99232FoNA",
    "https://youtu.be/5BHWywnBhhA",
    "https://youtu.be/oXzV9TzKEbo",
    "https://youtu.be/UHPY3CIx6G4"
]

def main():
    print("Starting knowledge base creation process...")
    knowledge_base = DexKitKnowledgeBase()
    
    print(f"Processing {len(YOUTUBE_URLS)} videos...")
    knowledge_base.create_knowledge_base(
        pdf_directory="./docs",
        youtube_urls=YOUTUBE_URLS
    )
    print("Knowledge base created successfully!")

if __name__ == "__main__":
    main() 