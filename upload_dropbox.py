import dropbox

DROPBOX_TOKEN = "sl.u.AGMwnyGobLVUT4R72OJpQrxZD3Hvb3Q9zD_52ttnqnyZKQJdiU15FLY16NQZKlu8Eap4InQQWS36XSJzXloXGq1HjxDBec2RBE3xdcmq4MlSj_VXmSUKeGbXs6u24_Q5GCQ3ByK58njDuw7iO688Yu4McNek_G6RH1ULvu8aMXXpF_2s7VRnN8a6A3t-joNnvLBto7EZzowIcSOrkBRytBYRU92dooGGKPZLDAioWK5vhqSluHL3IGmuY9v42WPSq3T31SJfUCGjnGwWhfo46NHQwPS2RMYgwpBcBooPedx6O2aXfFM6Exv-qXzX1mIIFGjZJYgN6ermnnOkFTODI0EnXclmvJWMu3gNU6sIlbF-mDhcN8S--AOOQzqG4QAMF3EF1M85VCld04Y_Zv2EhPgKsdxg10VIP-hXJqEjsTK8TiLrUHgw1jV6xagTqywpG1o9mXU-0RHbrQPdv0BkxNZGst2RBRgeLEaeu_Hk4y3a7Ia9veGCjUFpAOB8b0Z0jjQjt258IpTbnNMf-Uxt3WwpC5yiD_H3dGKnWIOwXrsML2ZJAQM8e-ypK99Y21VkBr8SX1t3ObOFz-PfaFomqQCL9eMwCy1nr-OsIV2lSlukHCUILxcESmW04CozCrDmvPMPcZEPSnrz2XHkdrhIdVlhKzLKBeRwWENT6Duuv1pHrj42F68DgRo-w2ozeSzZr4FmY1ShpZBsqdSXLPlVQ9XQ0fhi_WIeDKgmruGsWz6UwrOimJVEln7mC44sjMEY5kQzJZgyISvX5kj7zOaCjPsde2x8_zlp7oyivd7pll9g1rtcWEGFDzJGCORNfH0gD6r0kX9cfirAt2Pnrs5yF6CGM2mevaj1x8Hu8FPECXPKwgucKtmoh5OZkIThYrAoZmB0fyJ0L304AlrHfEM-IuVLnod8wxDs1Aq77F7l8n7fx_0CZoA7bn404t00DwB9EQQg_v8zxziohF6qDPfI56fS1EXg_QzwzA8L50JuUPTJSINcbGiFDSf9woV8AgDtlSrkdOTfNvZeCEoXgjE4-pzOz9JAiKJI5GAXuyR1oETfPaO4BoaJtObWgpPFMjD1iQB4k9mzHR4EKuUCKLoHRX1804FuhdUSaX-IYcFkIBS5_CgjB8k5HZjDYpckt_F61CESjx96eVPtMmHs4UPbyAoOq2wjRuzFip-ZHNC1OWixUhrYDDGiJxt3grKxfPTNhG9RJ7LzbWFFhXG3-ojYb6ASZGRMIaRhr0TzXZ0ZiQjWiHEJjuXhEgu7Xzv15VYtolLYUa7Vf_H5y_NtHc0ko3piWSNzJI46oTcmSBVkISP4RDTZgDRgri0GGKV6i8SOuYm-YGlWLf-cUN8D26eznzuji0inQVafMZ_SBKFPayicyPCaFtqpaL1XwVhngzlACjMFYy8-nlG2yJBLigoVVekz5dDNaBa9NIUznmoj95vIEg"
LOCAL_FILE = "besthome.zip"
DROPBOX_PATH = "/besthome.zip"
LAST_LINK_FILE = "last_db_link.txt"


def upload_and_get_link():
    dbx = dropbox.Dropbox(DROPBOX_TOKEN)

    # Upload
    with open(LOCAL_FILE, "rb") as f:
        dbx.files_upload(f.read(), DROPBOX_PATH, mode=dropbox.files.WriteMode.overwrite)

    print("✅ Dropbox upload tamamlandı")

    # Köhnə linkləri sil (varsa)
    try:
        links = dbx.sharing_list_shared_links(path=DROPBOX_PATH).links
        for l in links:
            dbx.sharing_revoke_shared_link(l.url)
    except Exception:
        pass

    # Yeni paylaşım linki yarat
    link = dbx.sharing_create_shared_link_with_settings(DROPBOX_PATH).url

    # Direct download üçün çevir
    direct_link = link.replace("?dl=0", "?dl=1")
    print("🔗 Dropbox link:", direct_link)

    # Linki fayla yaz
    with open(LAST_LINK_FILE, "w", encoding="utf-8") as f:
        f.write(direct_link)

    return direct_link


if __name__ == "__main__":
    upload_and_get_link()
