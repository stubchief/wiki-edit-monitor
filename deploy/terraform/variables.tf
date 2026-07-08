variable "folder_id" {
  description = "Yandex Cloud folder ID"
  type        = string
}

variable "zone" {
  type    = string
  default = "ru-central1-a"
}

variable "vm_name" {
  type    = string
  default = "wiki-edit-monitor"
}

variable "platform_id" {
  type    = string
  default = "standard-v3"
}

variable "cores" {
  type    = number
  default = 4
}

variable "memory" {
  type    = number
  default = 4
}

variable "disk_size" {
  type    = number
  default = 20
}

variable "image_family" {
  type    = string
  default = "ubuntu-2204-lts"
}

variable "ssh_public_key_path" {
  description = "Path to local SSH public key"
  type        = string
}

variable "repo_url" {
  type    = string
  default = "https://github.com/stubchief/wiki-edit-monitor.git"
}
